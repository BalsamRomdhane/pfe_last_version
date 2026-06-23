"""
LLM Service — Ollama integration for compliance chat.
Provides RAG-based compliance answers using local LLM.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Generator, List

import requests

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_URL   = os.getenv('OLLAMA_URL',   'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:3b')
LLM_ENABLED  = os.getenv('LLM_ENABLED',  'true').lower() in ('true', '1', 'yes')
LLM_TIMEOUT  = int(os.getenv('LLM_TIMEOUT', '120'))


# ── Availability ──────────────────────────────────────────────────────────────
def get_ollama_status() -> Dict[str, Any]:
    """Check Ollama availability and list loaded models."""
    if not LLM_ENABLED:
        return {'available': False, 'model': OLLAMA_MODEL, 'reason': 'LLM_ENABLED=false'}

    try:
        resp = requests.get(f'{OLLAMA_URL}/api/tags', timeout=5)
        if resp.status_code == 200:
            models = [m['name'] for m in resp.json().get('models', [])]
            return {
                'available': True,
                'model': OLLAMA_MODEL,
                'models': models,
                'url': OLLAMA_URL,
            }
        return {'available': False, 'model': OLLAMA_MODEL, 'reason': f'HTTP {resp.status_code}'}
    except Exception as e:
        return {'available': False, 'model': OLLAMA_MODEL, 'reason': str(e)}


def pull_model(model: str) -> Dict[str, Any]:
    """Pull/download a model in Ollama."""
    try:
        resp = requests.post(
            f'{OLLAMA_URL}/api/pull',
            json={'name': model, 'stream': False},
            timeout=300,
        )
        if resp.status_code == 200:
            return {'success': True, 'model': model}
        return {'success': False, 'model': model, 'reason': resp.text[:200]}
    except Exception as e:
        return {'success': False, 'model': model, 'reason': str(e)}


# ── RAG answer generation ────────────────────────────────────────────────────
def _build_prompt(question: str, context_rules: List[Dict], context_evidence: List[Dict]) -> str:
    """Build a RAG prompt from retrieved rules and evidence."""
    rule_ctx = '\n'.join(
        f"- [{r.get('severity','?')}] {r.get('title','')}: {r.get('description','')}"
        for r in context_rules[:10]
    )
    evidence_ctx = '\n'.join(
        f"- [{e.get('label','?')}] {e.get('rule_title','')}: {e.get('evidence_text','')[:200]}"
        for e in context_evidence[:10]
    )

    return f"""You are a compliance expert assistant. Answer the following question based on the compliance rules and evidence provided.

COMPLIANCE RULES:
{rule_ctx or 'No rules found.'}

EVIDENCE:
{evidence_ctx or 'No evidence found.'}

QUESTION: {question}

Provide a clear, concise answer based only on the information above. If the answer is not in the provided context, say so."""


def generate_compliance_answer(
    question: str,
    context_rules=None,
    context_evidence=None,
    standard: str = '',
    # Legacy parameter names used by compliance_chat_api
    evidences=None,
    user: str = 'anonymous',
) -> dict:
    """Generate a compliance answer using Ollama LLM with RAG context.
    
    Accepts both new signature (context_rules, context_evidence) and
    legacy signature (evidences) from compliance_chat_api.
    """
    # Normalise: legacy 'evidences' param maps to context_evidence
    if evidences is not None and context_evidence is None:
        context_evidence = evidences
    context_rules    = context_rules    or []
    context_evidence = context_evidence or []
    status = get_ollama_status()
    if not status.get('available'):
        return _keyword_fallback(question, context_rules, context_evidence)

    prompt = _build_prompt(question, context_rules, context_evidence)

    try:
        resp = requests.post(
            f'{OLLAMA_URL}/api/generate',
            json={
                'model': OLLAMA_MODEL,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': 0.1,
                    'num_predict': 512,
                    'num_ctx': 2048,
                },
            },
            timeout=LLM_TIMEOUT,
        )
        if resp.status_code == 200:
            answer = resp.json().get('response', '')
            return {
                'answer': answer,
                'model': OLLAMA_MODEL,
                'sources': context_rules[:5],
                'fallback': False,
            }
        return _keyword_fallback(question, context_rules, context_evidence)
    except Exception as e:
        logger.error('LLM generate failed: %s', e)
        return _keyword_fallback(question, context_rules, context_evidence)


def stream_compliance_answer(
    question: str,
    context_rules: List[Dict],
    context_evidence: List[Dict],
    standard: str = '',
) -> Generator[str, None, None]:
    """Stream compliance answer tokens."""
    status = get_ollama_status()
    if not status.get('available'):
        fallback = _keyword_fallback(question, context_rules, context_evidence)
        yield fallback['answer']
        return

    prompt = _build_prompt(question, context_rules, context_evidence)

    try:
        resp = requests.post(
            f'{OLLAMA_URL}/api/generate',
            json={
                'model': OLLAMA_MODEL,
                'prompt': prompt,
                'stream': True,
                'options': {'temperature': 0.1, 'num_predict': 512, 'num_ctx': 2048},
            },
            stream=True,
            timeout=LLM_TIMEOUT,
        )
        import json as _json
        for line in resp.iter_lines():
            if line:
                try:
                    chunk = _json.loads(line)
                    token = chunk.get('response', '')
                    if token:
                        yield token
                    if chunk.get('done'):
                        break
                except Exception:
                    continue
    except Exception as e:
        logger.error('LLM stream failed: %s', e)
        fallback = _keyword_fallback(question, context_rules, context_evidence)
        yield fallback['answer']


def _keyword_fallback(
    question: str,
    context_rules: List[Dict],
    context_evidence: List[Dict],
) -> Dict[str, Any]:
    """Keyword-based fallback when LLM is unavailable."""
    q_lower = question.lower()
    relevant_rules = [r for r in context_rules if any(w in r.get('title', '').lower() for w in q_lower.split() if len(w) > 3)]
    relevant_ev    = [e for e in context_evidence if any(w in e.get('evidence_text', '').lower() for w in q_lower.split() if len(w) > 3)]

    if relevant_rules or relevant_ev:
        parts = []
        if relevant_rules:
            parts.append('Relevant rules:\n' + '\n'.join(f"- {r['title']}" for r in relevant_rules[:5]))
        if relevant_ev:
            parts.append('Related evidence:\n' + '\n'.join(f"- {e.get('rule_title','')}: {e.get('evidence_text','')[:150]}" for e in relevant_ev[:5]))
        answer = '\n\n'.join(parts)
    else:
        answer = f"No specific compliance information found for: '{question}'. Please consult the compliance documentation directly."

    return {'answer': answer, 'model': 'keyword-fallback', 'sources': context_rules[:5], 'fallback': True}
