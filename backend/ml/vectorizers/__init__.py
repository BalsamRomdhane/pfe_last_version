"""
Vectorization module for semantic representation.
Supports TF-IDF, Word2Vec, and FastText embeddings.
"""

import os
import pickle
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    from gensim.models import Word2Vec, FastText
except ImportError:
    Word2Vec = None
    FastText = None

logger = logging.getLogger(__name__)


class VectorizerManager:
    """Manages different vectorization techniques."""

    def __init__(self, models_dir: str = None):
        """
        Initialize vectorizer manager.

        Args:
            models_dir: Directory to store/load vector models
        """
        if models_dir is None:
            models_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
        self.models_dir = models_dir
        os.makedirs(self.models_dir, exist_ok=True)

        self.tfidf_vectorizer = None
        self.word2vec_model = None
        self.fasttext_model = None

    def fit_tfidf(self, documents: List[str], **kwargs) -> 'TfidfVectorizer':
        """
        Fit TF-IDF vectorizer on documents.

        Args:
            documents: List of document texts
            **kwargs: Additional parameters for TfidfVectorizer

        Returns:
            Fitted TF-IDF vectorizer
        """
        # Use min_df=1 so small corpora (e.g. 7 rule texts) are not filtered to empty.
        # No stop_words — content is French; English stop words remove useful terms.
        default_params = {
            'max_features': 5000,
            'min_df': 1,
            'max_df': 1.0,
            'ngram_range': (1, 2),
            'stop_words': None,
            'analyzer': 'word',
            'lowercase': True,
        }
        default_params.update(kwargs)

        self.tfidf_vectorizer = TfidfVectorizer(**default_params)
        self.tfidf_vectorizer.fit(documents)

        # Save the vectorizer
        self._save_model(self.tfidf_vectorizer, 'tfidf_vectorizer.pkl')

        return self.tfidf_vectorizer

    def load_tfidf(self) -> Optional['TfidfVectorizer']:
        """Load TF-IDF vectorizer from disk."""
        return self._load_model('tfidf_vectorizer.pkl')

    def transform_tfidf(self, documents: List[str]) -> Optional[np.ndarray]:
        """
        Transform documents using TF-IDF.

        Args:
            documents: List of document texts

        Returns:
            TF-IDF matrix
        """
        if self.tfidf_vectorizer is None:
            self.tfidf_vectorizer = self.load_tfidf()

        if self.tfidf_vectorizer is None:
            logger.error("TF-IDF vectorizer not fitted or loaded")
            return None

        return self.tfidf_vectorizer.transform(documents).toarray()

    def train_word2vec(self, sentences: List[List[str]], **kwargs) -> Optional['Word2Vec']:
        """
        Train Word2Vec model.

        Args:
            sentences: List of tokenized sentences
            **kwargs: Additional parameters for Word2Vec

        Returns:
            Trained Word2Vec model
        """
        if Word2Vec is None:
            logger.error("gensim not installed")
            return None

        default_params = {
            'vector_size': 100,
            'window': 5,
            'min_count': 2,
            'workers': 4,
            'epochs': 10
        }
        default_params.update(kwargs)

        self.word2vec_model = Word2Vec(sentences, **default_params)
        self._save_model(self.word2vec_model, 'word2vec.model')

        return self.word2vec_model

    def load_word2vec(self) -> Optional['Word2Vec']:
        """Load Word2Vec model from disk."""
        return self._load_model('word2vec.model')

    def get_word2vec_vector(self, words: List[str]) -> Optional[np.ndarray]:
        """
        Get vector representation for a list of words using Word2Vec.

        Args:
            words: List of words

        Returns:
            Average vector or None
        """
        if self.word2vec_model is None:
            self.word2vec_model = self.load_word2vec()

        if self.word2vec_model is None:
            return None

        vectors = []
        for word in words:
            if word in self.word2vec_model.wv:
                vectors.append(self.word2vec_model.wv[word])

        if vectors:
            return np.mean(vectors, axis=0)
        else:
            return np.zeros(self.word2vec_model.vector_size)

    def train_fasttext(self, sentences: List[List[str]], **kwargs) -> Optional['FastText']:
        """
        Train FastText model.

        Args:
            sentences: List of tokenized sentences
            **kwargs: Additional parameters for FastText

        Returns:
            Trained FastText model
        """
        if FastText is None:
            logger.error("gensim not installed")
            return None

        default_params = {
            'vector_size': 100,
            'window': 5,
            'min_count': 2,
            'workers': 4,
            'epochs': 10
        }
        default_params.update(kwargs)

        self.fasttext_model = FastText(sentences, **default_params)
        self._save_model(self.fasttext_model, 'fasttext.model')

        return self.fasttext_model

    def load_fasttext(self) -> Optional['FastText']:
        """Load FastText model from disk."""
        return self._load_model('fasttext.model')

    def get_fasttext_vector(self, words: List[str]) -> Optional[np.ndarray]:
        """
        Get vector representation for a list of words using FastText.

        Args:
            words: List of words

        Returns:
            Average vector or None
        """
        if self.fasttext_model is None:
            self.fasttext_model = self.load_fasttext()

        if self.fasttext_model is None:
            return None

        vectors = []
        for word in words:
            try:
                vectors.append(self.fasttext_model.wv[word])
            except KeyError:
                continue

        if vectors:
            return np.mean(vectors, axis=0)
        else:
            return np.zeros(self.fasttext_model.vector_size)

    def compute_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score
        """
        if vec1 is None or vec2 is None:
            return 0.0

        # Ensure vectors are 2D
        vec1 = vec1.reshape(1, -1) if vec1.ndim == 1 else vec1
        vec2 = vec2.reshape(1, -1) if vec2.ndim == 1 else vec2

        try:
            similarity = cosine_similarity(vec1, vec2)[0][0]
            return float(similarity)
        except Exception as e:
            logger.error(f"Error computing similarity: {e}")
            return 0.0

    def find_similar_documents(self, query_vector: np.ndarray,
                             document_vectors: np.ndarray,
                             top_k: int = 5) -> List[Tuple[int, float]]:
        """
        Find most similar documents using cosine similarity.

        Args:
            query_vector: Query vector
            document_vectors: Document vectors matrix
            top_k: Number of top similar documents to return

        Returns:
            List of (index, similarity_score) tuples
        """
        if query_vector is None or document_vectors is None:
            return []

        query_vector = query_vector.reshape(1, -1)
        similarities = cosine_similarity(query_vector, document_vectors)[0]

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        return [(int(idx), float(similarities[idx])) for idx in top_indices]

    def _save_model(self, model: Any, filename: str):
        """Save model to disk."""
        try:
            filepath = os.path.join(self.models_dir, filename)
            with open(filepath, 'wb') as f:
                pickle.dump(model, f)
            logger.info(f"Model saved to {filepath}")
        except Exception as e:
            logger.error(f"Error saving model {filename}: {e}")

    def _load_model(self, filename: str) -> Any:
        """Load model from disk."""
        try:
            filepath = os.path.join(self.models_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    model = pickle.load(f)
                logger.info(f"Model loaded from {filepath}")
                return model
            else:
                logger.warning(f"Model file not found: {filepath}")
                return None
        except Exception as e:
            logger.error(f"Error loading model {filename}: {e}")
            return None