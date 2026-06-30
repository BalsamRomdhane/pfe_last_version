import os
import re
import pickle
import threading
import time
from datetime import timezone

import numpy as np
from django.utils import timezone as tz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    import faiss
    FAISS_AVAILABLE = True
except (ImportError, OSError, Exception):
    FAISS_AVAILABLE = False

SENTENCE_TRANSFORMERS_AVAILABLE = False
SentenceTransformer = None

from api.models import Document
from api.utils import RULE_KEYWORDS, extract_document_text, normalize_text

EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'

# ── Singleton cache — modèle ST chargé une seule fois par process ────────────
_MODEL_CACHE: dict = {}

# ── Cache FAISS en mémoire ─────────────────────────────────────────────────
# Évite de relire les fichiers FAISS depuis le disque à chaque requête chat.
# Structure : (index, ids, vectorizer, vectors, meta, mtime)
_EVIDENCE_INDEX_CACHE: tuple | None = None
_EVIDENCE_INDEX_LOCK  = threading.Lock()
_EVIDENCE_INDEX_MTIME: float = 0.0   # mtime du fichier .faiss — invalide le cache si modifié

# Cache LRU des vecteurs de requête (question → vecteur)
# Évite de recalculer l'embedding pour des questions répétées (suggestions, retry).
_QUERY_VECTOR_CACHE: dict = {}
_QUERY_VECTOR_CACHE_MAX = 128


def _get_sentence_transformer(model_name: str = EMBEDDING_MODEL_NAME):
    """
    Return a cached SentenceTransformer instance.
    The model is loaded once per process and reused across all requests,
    eliminating the ~2-3s cold-start penalty on every semantic search call.
    """
    global SENTENCE_TRANSFORMERS_AVAILABLE, SentenceTransformer, _MODEL_CACHE

    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]

    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            from sentence_transformers import SentenceTransformer as ST
            SentenceTransformer = ST
            SENTENCE_TRANSFORMERS_AVAILABLE = True
        except (ImportError, OSError, Exception):
            raise ImportError(
                "sentence-transformers is not available. "
                "Install it with: pip install sentence-transformers"
            )

    model = SentenceTransformer(model_name)
    _MODEL_CACHE[model_name] = model
    return model


class SemanticSearchEngine:
    def __init__(self, model_name=EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        # Use cached model — no reload on every instantiation
        self.model = _get_sentence_transformer(model_name)

    def _build_embedding_matrix(self, documents):
        texts = [normalize_text(value['text']) for value in documents]
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        embeddings = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return embeddings

    def _build_faiss_index(self, vectors):
        dim = vectors.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(vectors)
        return index

    def _compute_bm25_scores(self, documents, query):
        texts = [normalize_text(value['text']) for value in documents]
        if not texts:
            return np.zeros((0,), dtype=float)

        vectorizer = TfidfVectorizer(stop_words='english')
        try:
            doc_matrix = vectorizer.fit_transform(texts)
            query_vec = vectorizer.transform([query])
            scores = cosine_similarity(query_vec, doc_matrix)[0]
            return scores
        except ValueError:
            return np.zeros((len(texts),), dtype=float)

    def _calculate_keyword_score(self, text, standard):
        if not standard or standard not in RULE_KEYWORDS:
            return 0.0

        keywords = RULE_KEYWORDS.get(standard, {})
        text_lower = text.lower()
        matched = 0
        for rule, terms in keywords.items():
            for term in terms:
                if term.lower() in text_lower:
                    matched += 1
                    break

        total_rules = len(keywords)
        if total_rules == 0:
            return 0.0
        return min(1.0, matched / total_rules)

    def _extract_evidence(self, text, standard):
        snippets = []
        rules = RULE_KEYWORDS.get(standard, {}) if standard else {}
        text_lower = text.lower()

        for rule, terms in rules.items():
            for term in terms:
                pos = text_lower.find(term.lower())
                if pos >= 0:
                    start = max(0, pos - 60)
                    end = min(len(text), pos + len(term) + 60)
                    snippet = text[start:end].strip()
                    snippets.append({
                        'rule': rule,
                        'keyword': term,
                        'snippet': snippet,
                    })
                    break

        return snippets[:5]

    def search(self, query, standard=None, top_k=5):
        if not query or not isinstance(query, str):
            raise ValueError('Query must be a non-empty string.')

        document_qs = Document.objects.select_related('norme').all()
        if standard:
            document_qs = document_qs.filter(norme__name=standard)

        document_records = []
        for document in document_qs:
            text = extract_document_text(document)
            if not text:
                continue
            document_records.append({
                'id': document.id,
                'text': text,
                'standard': document.norme.name if document.norme else None,
                'status': document.status,
                'document_name': os.path.basename(document.file.name) if document.file else None,
            })

        if not document_records:
            return {
                'query': query,
                'standard': standard,
                'results': [],
                'message': 'No indexed documents were found for this standard.',
            }

        # Semantic embedding scores
        doc_embeddings = self._build_embedding_matrix(document_records)
        query_embedding = self.model.encode([normalize_text(query)], convert_to_numpy=True, normalize_embeddings=True)

        if FAISS_AVAILABLE and doc_embeddings.shape[0] > 0:
            index = self._build_faiss_index(doc_embeddings)
            distances, indices = index.search(query_embedding, min(top_k, len(document_records)))
            semantic_scores = distances[0].tolist()
            order = indices[0].tolist()
        else:
            semantic_scores = cosine_similarity(query_embedding, doc_embeddings)[0].tolist()
            order = list(np.argsort([-score for score in semantic_scores]))

        bm25_scores = self._compute_bm25_scores(document_records, query)
        keyword_scores = [self._calculate_keyword_score(value['text'], standard) for value in document_records]

        combined = []
        for idx, record in enumerate(document_records):
            combined_score = (
                0.55 * semantic_scores[idx]
                + 0.30 * bm25_scores[idx]
                + 0.15 * keyword_scores[idx]
            )
            combined.append({
                'index': idx,
                'document_id': record['id'],
                'document_name': record['document_name'],
                'standard': record['standard'],
                'status': record['status'],
                'semantic_score': float(np.clip(semantic_scores[idx], 0.0, 1.0)),
                'bm25_score': float(np.clip(bm25_scores[idx], 0.0, 1.0)),
                'keyword_score': float(np.clip(keyword_scores[idx], 0.0, 1.0)),
                'hybrid_score': float(np.clip(combined_score, 0.0, 1.0)),
                'evidence': self._extract_evidence(record['text'], standard),
            })

        combined.sort(key=lambda item: item['hybrid_score'], reverse=True)
        top_results = combined[:top_k]

        return {
            'query': query,
            'standard': standard,
            'total_documents': len(document_records),
            'results': top_results,
        }


def build_and_persist_evidence_index(standard=None, norme_id=None, model_name=EMBEDDING_MODEL_NAME):
    """Build an evidence search index from RuleTrainingSample.evidence_text and persist metadata.

    Supports sentence-transformers embeddings plus FAISS persistence, with TF-IDF fallback when needed.
    Returns a metadata dict with counts and paths.
    """
    try:
        from api.models import RuleTrainingSample
    except Exception:
        raise RuntimeError('Could not import RuleTrainingSample model')

    # Filter samples
    qs = RuleTrainingSample.objects.all()
    if norme_id:
        try:
            qs = qs.filter(norm_id=int(norme_id))
        except Exception:
            qs = qs.filter(norm__name__iexact=norme_id)
    elif standard:
        qs = qs.filter(norm__name__iexact=standard)

    samples = list(qs.order_by('created_at').values('id', 'evidence_text'))
    total = len(samples)

    texts = [normalize_text(s['evidence_text'] or '') for s in samples]
    ids = [int(s['id']) for s in samples]

    if not texts:
        raise RuntimeError('No evidence texts found to index')

    # Compute embeddings
    vectors = None
    used_model = None
    if SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            model = _get_sentence_transformer(model_name)  # use cached singleton
            used_model = model_name
            vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        except Exception:
            vectors = None

    if vectors is None:
        # Fallback to TF-IDF dense vectors
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1024)
        try:
            mat = vectorizer.fit_transform(texts)
            vectors = mat.toarray().astype('float32')
            used_model = 'tfidf-fallback'
        except Exception as e:
            raise RuntimeError(f'Failed to vectorize texts: {e}')

    # Ensure dtype float32
    import numpy as np
    vectors = np.asarray(vectors, dtype=np.float32)

    models_dir = os.path.join(os.path.dirname(__file__), 'models')
    os.makedirs(models_dir, exist_ok=True)
    index_path = os.path.join(models_dir, 'evidence_index.faiss')
    ids_path = os.path.join(models_dir, 'evidence_index_ids.json')
    vec_path = os.path.join(models_dir, 'evidence_vectorizer.pkl')
    vec_matrix_path = os.path.join(models_dir, 'evidence_vectors.npy')
    meta_path = os.path.join(models_dir, 'evidence_index_meta.json')

    indexed = 0
    meta = {
        'total_evidences': total,
        'indexed_evidences': 0,
        'embedding_model': used_model,
        'vector_dim': int(vectors.shape[1]) if vectors.ndim == 2 else 0,
        'last_trained': None,
        'index_path': index_path,
        'ids_path': ids_path,
        'vectorizer_path': vec_path,
        'vector_matrix_path': vec_matrix_path,
    }

    # Persist ids mapping and optional artifacts
    import json
    with open(ids_path, 'w', encoding='utf-8') as fh:
        json.dump(ids, fh)

    # Persist raw vector matrix for fallback search when FAISS is unavailable.
    try:
        np.save(vec_matrix_path, vectors)
    except Exception as e:
        raise RuntimeError(f'Failed to persist evidence vectors: {e}')

    if used_model == 'tfidf-fallback' and vectorizer is not None:
        try:
            with open(vec_path, 'wb') as fh:
                pickle.dump(vectorizer, fh)
        except Exception as e:
            raise RuntimeError(f'Failed to persist TF-IDF artifacts: {e}')

    if FAISS_AVAILABLE and vectors.shape[0] > 0:
        try:
            dim = vectors.shape[1]
            index = faiss.IndexFlatIP(dim)
            index.add(vectors)
            faiss.write_index(index, index_path)
            indexed = int(index.ntotal)
            meta['indexed_evidences'] = indexed
            meta['last_trained'] = tz.now().isoformat()
            # write metadata
            with open(meta_path, 'w', encoding='utf-8') as fh:
                json.dump(meta, fh, indent=2)
            # Invalider le cache en mémoire après rebuild
            invalidate_evidence_index_cache()
            return meta
        except Exception as e:
            raise RuntimeError(f'Failed to build or persist FAISS index: {e}')
    else:
        # FAISS not available: save metadata and TF-IDF fallback artifacts if present
        meta['indexed_evidences'] = len(ids)
        meta['last_trained'] = tz.now().isoformat()
        with open(meta_path, 'w', encoding='utf-8') as fh:
            json.dump(meta, fh, indent=2)
        # Invalider le cache en mémoire après rebuild
        invalidate_evidence_index_cache()
        return meta


def load_evidence_index_metadata():
    models_dir = os.path.join(os.path.dirname(__file__), 'models')
    meta_path = os.path.join(models_dir, 'evidence_index_meta.json')
    if not os.path.exists(meta_path):
        return None
    import json
    with open(meta_path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def load_evidence_index():
    """
    Load FAISS index, ids, vectorizer, vectors et metadata.

    OPTIMISATION : cache en mémoire process-level avec invalidation par mtime.
    - Première lecture : charge depuis disque (~180ms)
    - Requêtes suivantes : retourne le tuple en cache (~0.1ms)
    - Invalidation automatique si le fichier .faiss est modifié (rebuild index)
    """
    global _EVIDENCE_INDEX_CACHE, _EVIDENCE_INDEX_MTIME

    models_dir = os.path.join(os.path.dirname(__file__), 'models')
    index_path = os.path.join(models_dir, 'evidence_index.faiss')
    ids_path = os.path.join(models_dir, 'evidence_index_ids.json')
    vec_path = os.path.join(models_dir, 'evidence_vectorizer.pkl')
    vec_matrix_path = os.path.join(models_dir, 'evidence_vectors.npy')

    # Détecter si les fichiers ont changé depuis le dernier chargement
    try:
        current_mtime = os.path.getmtime(ids_path) if os.path.exists(ids_path) else 0.0
    except OSError:
        current_mtime = 0.0

    with _EVIDENCE_INDEX_LOCK:
        if _EVIDENCE_INDEX_CACHE is not None and current_mtime == _EVIDENCE_INDEX_MTIME:
            # Cache valide — retour immédiat sans I/O disque
            return _EVIDENCE_INDEX_CACHE

        # Cache invalide ou absent — charger depuis disque
        meta = load_evidence_index_metadata()

        if meta is None or not os.path.exists(ids_path):
            raise RuntimeError('Persisted evidence index not found')

        if not os.path.exists(index_path) and not os.path.exists(vec_matrix_path):
            raise RuntimeError('Persisted evidence index not found')

        import json
        with open(ids_path, 'r', encoding='utf-8') as fh:
            ids = json.load(fh)

        # Charger l'index FAISS
        index = None
        if FAISS_AVAILABLE and os.path.exists(index_path):
            try:
                index = faiss.read_index(index_path)
            except Exception:
                index = None

        # Charger le vectorizer TF-IDF de fallback
        vectorizer = None
        if os.path.exists(vec_path):
            try:
                with open(vec_path, 'rb') as fh:
                    vectorizer = pickle.load(fh)
            except Exception:
                vectorizer = None

        # Charger la matrice de vecteurs
        vectors = None
        if os.path.exists(vec_matrix_path):
            try:
                vectors = np.load(vec_matrix_path)
            except Exception:
                vectors = None

        result = (index, ids, vectorizer, vectors, meta)
        _EVIDENCE_INDEX_CACHE = result
        _EVIDENCE_INDEX_MTIME = current_mtime
        return result


def invalidate_evidence_index_cache() -> None:
    """Forcer le rechargement de l'index au prochain appel (après rebuild)."""
    global _EVIDENCE_INDEX_CACHE, _EVIDENCE_INDEX_MTIME
    with _EVIDENCE_INDEX_LOCK:
        _EVIDENCE_INDEX_CACHE = None
        _EVIDENCE_INDEX_MTIME = 0.0


def embed_query_vector(text, model_name=EMBEDDING_MODEL_NAME, vectorizer=None):
    """
    Return a numpy float32 vector for the given text.

    OPTIMISATION : cache LRU sur la question normalisée.
    La même question posée deux fois (retry, suggestion) ne recalcule pas l'embedding.
    Cache limité à 128 entrées pour éviter une fuite mémoire.

    Uses sentence-transformers if available, otherwise uses provided TF-IDF vectorizer.
    """
    if not text:
        return None

    # Clé de cache = texte normalisé + nom du modèle
    norm = normalize_text(text)
    cache_key = f'{model_name}::{norm[:200]}'

    if cache_key in _QUERY_VECTOR_CACHE:
        return _QUERY_VECTOR_CACHE[cache_key]

    result = None

    if SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            model = _get_sentence_transformer(model_name)
            vec = model.encode([norm], convert_to_numpy=True, normalize_embeddings=True)
            result = np.asarray(vec, dtype=np.float32)
        except Exception:
            pass

    if result is None and vectorizer is not None:
        try:
            mat = vectorizer.transform([text])
            result = np.asarray(mat.toarray(), dtype=np.float32)
        except Exception:
            pass

    if result is None:
        # Fallback ultime : vecteur de comptage de tokens (très faible qualité)
        tokens = norm.split()
        vec = np.zeros((1, 128), dtype=np.float32)
        for i, t in enumerate(tokens[:128]):
            vec[0, i] = len(t)
        result = vec

    # Stocker dans le cache LRU (FIFO si dépassement)
    if len(_QUERY_VECTOR_CACHE) >= _QUERY_VECTOR_CACHE_MAX:
        oldest_key = next(iter(_QUERY_VECTOR_CACHE))
        del _QUERY_VECTOR_CACHE[oldest_key]
    _QUERY_VECTOR_CACHE[cache_key] = result

    return result
