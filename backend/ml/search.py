import os
import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
import pickle

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

SENTENCE_TRANSFORMERS_AVAILABLE = False
SentenceTransformer = None

from api.models import Document
from api.utils import RULE_KEYWORDS, extract_document_text, normalize_text

EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'


class SemanticSearchEngine:
    def __init__(self, model_name=EMBEDDING_MODEL_NAME):
        global SENTENCE_TRANSFORMERS_AVAILABLE, SentenceTransformer
        self.model_name = model_name
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                from sentence_transformers import SentenceTransformer
                SENTENCE_TRANSFORMERS_AVAILABLE = True
            except ImportError:
                raise ImportError("sentence-transformers is not available. Please install it with: pip install sentence-transformers")
        self.model = SentenceTransformer(model_name)

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
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(model_name)
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
            meta['last_trained'] = datetime.utcnow().isoformat() + 'Z'
            # write metadata
            with open(meta_path, 'w', encoding='utf-8') as fh:
                json.dump(meta, fh, indent=2)
            return meta
        except Exception as e:
            raise RuntimeError(f'Failed to build or persist FAISS index: {e}')
    else:
        # FAISS not available: save metadata and TF-IDF fallback artifacts if present
        meta['indexed_evidences'] = len(ids)
        meta['last_trained'] = datetime.utcnow().isoformat() + 'Z'
        with open(meta_path, 'w', encoding='utf-8') as fh:
            json.dump(meta, fh, indent=2)
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
    """Load persisted FAISS index, ids list and metadata."""
    models_dir = os.path.join(os.path.dirname(__file__), 'models')
    index_path = os.path.join(models_dir, 'evidence_index.faiss')
    ids_path = os.path.join(models_dir, 'evidence_index_ids.json')
    vec_path = os.path.join(models_dir, 'evidence_vectorizer.pkl')
    vec_matrix_path = os.path.join(models_dir, 'evidence_vectors.npy')
    meta = load_evidence_index_metadata()

    if meta is None or not os.path.exists(ids_path):
        raise RuntimeError('Persisted evidence index not found')

    if not os.path.exists(index_path) and not os.path.exists(vec_matrix_path):
        raise RuntimeError('Persisted evidence index not found')

    # Load ids
    import json
    with open(ids_path, 'r', encoding='utf-8') as fh:
        ids = json.load(fh)

    # Load FAISS index if available
    if FAISS_AVAILABLE and os.path.exists(index_path):
        try:
            index = faiss.read_index(index_path)
        except Exception:
            index = None
    else:
        index = None

    # Load TF-IDF vectorizer if present
    vectorizer = None
    if os.path.exists(vec_path):
        try:
            with open(vec_path, 'rb') as fh:
                vectorizer = pickle.load(fh)
        except Exception:
            vectorizer = None

    vectors = None
    if os.path.exists(vec_matrix_path):
        try:
            vectors = np.load(vec_matrix_path)
        except Exception:
            vectors = None

    return index, ids, vectorizer, vectors, meta


def embed_query_vector(text, model_name=EMBEDDING_MODEL_NAME, vectorizer=None):
    """Return a numpy float32 vector for the given text.

    Uses sentence-transformers if available, otherwise uses provided TF-IDF vectorizer.
    """
    if not text:
        return None

    if SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(model_name)
            vec = model.encode([normalize_text(text)], convert_to_numpy=True, normalize_embeddings=True)
            return np.asarray(vec, dtype=np.float32)
        except Exception:
            pass

    if vectorizer is not None:
        try:
            mat = vectorizer.transform([text])
            return np.asarray(mat.toarray(), dtype=np.float32)
        except Exception:
            pass

    # Last resort: simple token-count vector (very weak)
    tokens = normalize_text(text).split()
    vec = np.zeros((1, 128), dtype=np.float32)
    for i, t in enumerate(tokens[:128]):
        vec[0, i] = len(t)
    return vec
