import os
import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

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
