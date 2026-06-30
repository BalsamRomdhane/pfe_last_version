"""
chat_metrics.py — Métriques Prometheus du pipeline chat IA.

Collecte en mémoire process-level (pas de dépendance externe).
Exposées via l'endpoint existant GET /api/metrics/ (mlops_prometheus_metrics_api).

Métriques collectées :
  chat_requests_total          — nombre total de requêtes chat
  chat_cache_hits_total        — réponses servies depuis le cache Django
  chat_faiss_duration_seconds  — temps de recherche FAISS + embed
  chat_db_duration_seconds     — temps de fetch DB (RuleTrainingSample)
  chat_llm_duration_seconds    — temps d'appel Ollama
  chat_total_duration_seconds  — temps total end-to-end
  chat_tokens_total            — nombre de tokens générés (estimé)
  chat_ollama_available        — 1 si Ollama en ligne, 0 sinon

Usage dans les vues :
    from services.chat_metrics import record_chat_request, record_faiss_time, ...
"""
from __future__ import annotations

import threading
import time
from typing import Optional

# ── Compteurs thread-safe ─────────────────────────────────────────────────────
_lock = threading.Lock()

_metrics: dict = {
    'chat_requests_total':         0,
    'chat_cache_hits_total':       0,
    'chat_stream_requests_total':  0,
    'chat_faiss_duration_sum':     0.0,
    'chat_faiss_duration_count':   0,
    'chat_db_duration_sum':        0.0,
    'chat_db_duration_count':      0,
    'chat_llm_duration_sum':       0.0,
    'chat_llm_duration_count':     0,
    'chat_total_duration_sum':     0.0,
    'chat_total_duration_count':   0,
    'chat_tokens_total':           0,
    'chat_ollama_available':       -1,   # -1 = inconnu
    'chat_fallback_total':         0,
    'faiss_cache_hits_total':      0,
    'embed_cache_hits_total':      0,
}


def _inc(key: str, value: float = 1.0) -> None:
    with _lock:
        _metrics[key] = _metrics.get(key, 0) + value


# ── API publique ──────────────────────────────────────────────────────────────

def record_chat_request() -> None:
    _inc('chat_requests_total')


def record_cache_hit() -> None:
    _inc('chat_cache_hits_total')


def record_stream_request() -> None:
    _inc('chat_stream_requests_total')


def record_faiss_time(duration_s: float) -> None:
    _inc('chat_faiss_duration_sum', duration_s)
    _inc('chat_faiss_duration_count')


def record_db_time(duration_s: float) -> None:
    _inc('chat_db_duration_sum', duration_s)
    _inc('chat_db_duration_count')


def record_llm_time(duration_s: float, tokens: int = 0, fallback: bool = False) -> None:
    _inc('chat_llm_duration_sum', duration_s)
    _inc('chat_llm_duration_count')
    if tokens > 0:
        _inc('chat_tokens_total', tokens)
    if fallback:
        _inc('chat_fallback_total')


def record_total_time(duration_s: float) -> None:
    _inc('chat_total_duration_sum', duration_s)
    _inc('chat_total_duration_count')


def record_ollama_status(available: bool) -> None:
    with _lock:
        _metrics['chat_ollama_available'] = 1 if available else 0


def record_faiss_cache_hit() -> None:
    _inc('faiss_cache_hits_total')


def record_embed_cache_hit() -> None:
    _inc('embed_cache_hits_total')


def get_snapshot() -> dict:
    """Retourne une copie thread-safe des métriques courantes."""
    with _lock:
        return dict(_metrics)


# ── Générateur Prometheus text format ────────────────────────────────────────

def generate_prometheus_lines() -> str:
    """
    Génère les lignes Prometheus text format pour le pipeline chat.
    Appelé depuis mlops_service.get_prometheus_metrics().
    """
    snap = get_snapshot()

    def _avg(sum_key: str, count_key: str) -> float:
        c = snap.get(count_key, 0)
        return round(snap.get(sum_key, 0.0) / c, 4) if c > 0 else 0.0

    lines = [
        '',
        '# HELP chat_requests_total Total compliance chat requests (non-streaming)',
        '# TYPE chat_requests_total counter',
        f'chat_requests_total {snap["chat_requests_total"]}',
        '',
        '# HELP chat_stream_requests_total Total compliance chat streaming requests (SSE)',
        '# TYPE chat_stream_requests_total counter',
        f'chat_stream_requests_total {snap["chat_stream_requests_total"]}',
        '',
        '# HELP chat_cache_hits_total Requests served from Django cache (no LLM call)',
        '# TYPE chat_cache_hits_total counter',
        f'chat_cache_hits_total {snap["chat_cache_hits_total"]}',
        '',
        '# HELP faiss_cache_hits_total FAISS index served from memory cache',
        '# TYPE faiss_cache_hits_total counter',
        f'faiss_cache_hits_total {snap["faiss_cache_hits_total"]}',
        '',
        '# HELP embed_cache_hits_total Query embedding served from LRU cache',
        '# TYPE embed_cache_hits_total counter',
        f'embed_cache_hits_total {snap["embed_cache_hits_total"]}',
        '',
        '# HELP chat_faiss_avg_duration_seconds Average FAISS search + embed duration',
        '# TYPE chat_faiss_avg_duration_seconds gauge',
        f'chat_faiss_avg_duration_seconds {_avg("chat_faiss_duration_sum", "chat_faiss_duration_count")}',
        '',
        '# HELP chat_db_avg_duration_seconds Average DB fetch duration (RuleTrainingSample)',
        '# TYPE chat_db_avg_duration_seconds gauge',
        f'chat_db_avg_duration_seconds {_avg("chat_db_duration_sum", "chat_db_duration_count")}',
        '',
        '# HELP chat_llm_avg_duration_seconds Average Ollama LLM call duration',
        '# TYPE chat_llm_avg_duration_seconds gauge',
        f'chat_llm_avg_duration_seconds {_avg("chat_llm_duration_sum", "chat_llm_duration_count")}',
        '',
        '# HELP chat_total_avg_duration_seconds Average end-to-end chat duration',
        '# TYPE chat_total_avg_duration_seconds gauge',
        f'chat_total_avg_duration_seconds {_avg("chat_total_duration_sum", "chat_total_duration_count")}',
        '',
        '# HELP chat_tokens_total Estimated total tokens generated by LLM',
        '# TYPE chat_tokens_total counter',
        f'chat_tokens_total {snap["chat_tokens_total"]}',
        '',
        '# HELP chat_fallback_total Requests answered by keyword fallback (LLM unavailable)',
        '# TYPE chat_fallback_total counter',
        f'chat_fallback_total {snap["chat_fallback_total"]}',
        '',
    ]

    if snap['chat_ollama_available'] >= 0:
        lines += [
            '# HELP chat_ollama_available 1 if Ollama LLM is available, 0 otherwise',
            '# TYPE chat_ollama_available gauge',
            f'chat_ollama_available {snap["chat_ollama_available"]}',
            '',
        ]

    return '\n'.join(lines)


# ── Context manager pratique ─────────────────────────────────────────────────

class Timer:
    """Context manager pour mesurer une durée et l'enregistrer automatiquement."""

    def __init__(self, record_fn):
        self._record_fn = record_fn
        self._start: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self) -> 'Timer':
        self._start = time.monotonic()
        return self

    def __exit__(self, *_) -> None:
        self.elapsed = time.monotonic() - self._start
        self._record_fn(self.elapsed)
