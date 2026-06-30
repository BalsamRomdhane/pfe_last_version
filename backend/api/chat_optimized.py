"""
chat_optimized.py — Pipeline chat optimisé.

Ce module fournit _retrieve_evidences() : la fonction de recherche d'evidence
commune aux deux endpoints chat (compliance_chat_api et compliance_chat_stream_api).

OPTIMISATIONS :
  - Cache mémoire FAISS (load_evidence_index → 0.1ms au lieu de 180ms)
  - Cache LRU embeddings (embed_query_vector → 0.1ms pour questions répétées)
  - DB : .only() sur les colonnes utiles seulement
  - Keyword fallback réduit (2 champs LIKE au lieu de 3)
  - Cache Django 60s sur la réponse complète (compliance_chat_api uniquement)
"""
from __future__ import annotations

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def _retrieve_evidences(question: str, standard: str, top_k: int) -> List[Dict]:
    """
    Récupère les evidences pertinentes pour une question.

    Étapes :
      1. FAISS sémantique (cache mémoire)
      2. Fallback keyword (LIKE sur 2 champs, si < 3 résultats FAISS)
      3. Fallback standard (top approved, si toujours < 2 résultats)

    Returns list of dicts : {id, rule, evidence, decision, score}
    """
    from api.models import RuleTrainingSample

    evidences: List[Dict] = []

    # ── Étape 1 : Recherche FAISS (cache mémoire) ─────────────────────────
    try:
        from ml.search import load_evidence_index, embed_query_vector
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity as cos_sim

        index, ids, vectorizer, vectors, meta = load_evidence_index()

        qvec = embed_query_vector(
            question,
            model_name=(meta.get('embedding_model') if meta else None),
            vectorizer=vectorizer,
        )

        if qvec is not None:
            q = np.asarray(qvec, dtype=np.float32)

            if index is not None and getattr(index, 'ntotal', 0) > 0:
                distances, indices_arr = index.search(q, min(top_k, index.ntotal))
                hits = [
                    {'id': ids[idx], 'score': float(d)}
                    for dist_row, idx_row in zip(distances.tolist(), indices_arr.tolist())
                    for d, idx in zip(dist_row, idx_row)
                    if 0 <= idx < len(ids)
                ]
            elif vectorizer is not None and vectors is not None:
                if q.ndim == 1:
                    q = q.reshape(1, -1)
                sims = cos_sim(q, vectors.astype(np.float32))[0]
                top_idx = np.argsort(sims)[::-1][:top_k]
                hits = [{'id': ids[i], 'score': float(sims[i])} for i in top_idx]
            else:
                hits = []

            if hits:
                sample_ids = [h['id'] for h in hits]
                score_map  = {h['id']: h['score'] for h in hits}
                # only() : charge uniquement les colonnes nécessaires
                samples = (
                    RuleTrainingSample.objects
                    .filter(id__in=sample_ids)
                    .only('id', 'rule_title', 'evidence_text', 'label', 'rule_id')
                    .select_related('rule')
                )
                for s in samples:
                    evidences.append({
                        'id':       s.id,
                        'rule':     s.rule_title or (s.rule.title if s.rule else ''),
                        'evidence': s.evidence_text or '',
                        'decision': s.label,
                        'score':    round(max(0.0, min(1.0, score_map.get(s.id, 0))) * 100),
                    })

    except Exception as exc:
        logger.warning('Chat evidence search failed: %s', exc)

    # ── Étape 2 : Fallback keyword (si < 3 résultats) ─────────────────────
    if len(evidences) < 3:
        from django.db.models import Q as DQ

        words = [w for w in question[:80].split() if len(w) > 3]
        q_filter = DQ()
        for w in words[:4]:
            q_filter |= DQ(evidence_text__icontains=w) | DQ(rule_title__icontains=w)

        if q_filter:
            seen_ids = {e['id'] for e in evidences if 'id' in e}
            qs = (
                RuleTrainingSample.objects
                .filter(q_filter)
                .only('id', 'rule_title', 'evidence_text', 'label')
                .order_by('-confidence_score')[:top_k]
            )
            for s in qs:
                if s.id not in seen_ids:
                    evidences.append({
                        'id': s.id, 'rule': s.rule_title or '',
                        'evidence': s.evidence_text or '', 'decision': s.label, 'score': 50,
                    })

    # ── Étape 3 : Fallback standard (si toujours < 2) ─────────────────────
    if len(evidences) < 2:
        std_qs = RuleTrainingSample.objects.filter(label='approved')
        if standard:
            std_qs = std_qs.filter(norm__name__icontains=standard)
        for s in (
            std_qs
            .only('id', 'rule_title', 'evidence_text', 'label')
            .order_by('-confidence_score')[:top_k]
        ):
            evidences.append({
                'id': s.id, 'rule': s.rule_title or '',
                'evidence': s.evidence_text or '', 'decision': s.label, 'score': 40,
            })

    return evidences
