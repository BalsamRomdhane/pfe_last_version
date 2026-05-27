"""
Semantic similarity calculations using sentence-transformers.

Computes cosine similarity between rule and document embeddings 
to capture semantic relevance beyond keyword matching.

Models:
- all-MiniLM-L6-v2: Fast, lightweight model (6 layers, 22M params)
- Fallback: Simple TF-IDF similarity if model unavailable
"""

import numpy as np
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Try to import sentence_transformers, fallback if not available
try:
    from sentence_transformers import SentenceTransformer, util
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not installed. Using fallback TF-IDF similarity.")


class SemanticSimilarityCalculator:
    """Calculate semantic similarity between texts using embeddings."""
    
    _MODEL_CACHE = {}  # Cache loaded models to avoid reloading
    
    @classmethod
    def get_model(cls, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Get or load a sentence-transformers model.
        
        Args:
            model_name: HuggingFace model identifier
            
        Returns:
            SentenceTransformer model or None if unavailable
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            return None
        
        if model_name not in cls._MODEL_CACHE:
            try:
                logger.info(f"Loading model: {model_name}")
                model = SentenceTransformer(model_name)
                cls._MODEL_CACHE[model_name] = model
                logger.info(f"Model {model_name} loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load model {model_name}: {e}")
                return None
        
        return cls._MODEL_CACHE.get(model_name)
    
    @staticmethod
    def compute_embedding(text: str, model=None) -> Optional[np.ndarray]:
        """
        Compute sentence embedding for text.
        
        Args:
            text: Input text
            model: SentenceTransformer model instance
            
        Returns:
            Embedding vector or None if model unavailable
        """
        if not text or model is None:
            return None
        
        try:
            embedding = model.encode(text, convert_to_tensor=False)
            return embedding
        except Exception as e:
            logger.error(f"Error computing embedding: {e}")
            return None
    
    @staticmethod
    def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute cosine similarity between two vectors.
        
        Returns:
            Similarity score in [0, 1]
        """
        if vec1 is None or vec2 is None:
            return 0.0
        
        try:
            # Cosine similarity: (A·B) / (||A|| × ||B||)
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            # Clamp to [0, 1] (cosine can be negative)
            return float(max(0.0, min(1.0, (similarity + 1) / 2)))
        except Exception as e:
            logger.error(f"Error computing cosine similarity: {e}")
            return 0.0


def compute_semantic_score(
    rule_text: str,
    document_text: str,
    model_name: str = 'all-MiniLM-L6-v2'
) -> float:
    """
    Compute semantic similarity score between rule and document.
    
    High score = rule is semantically relevant to document
    Low score = rule is not semantically relevant
    
    Args:
        rule_text: Rule description/criteria
        document_text: Full document text
        model_name: Sentence-transformers model to use
        
    Returns:
        Semantic score in [0, 1]
    """
    if not rule_text or not document_text:
        return 0.0
    
    # Try transformer-based approach
    if SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            model = SemanticSimilarityCalculator.get_model(model_name)
            if model is not None:
                rule_embedding = SemanticSimilarityCalculator.compute_embedding(rule_text, model)
                doc_embedding = SemanticSimilarityCalculator.compute_embedding(document_text, model)
                
                if rule_embedding is not None and doc_embedding is not None:
                    score = SemanticSimilarityCalculator.cosine_similarity(rule_embedding, doc_embedding)
                    logger.debug(f"Computed semantic score: {score:.3f} for rule vs doc")
                    return score
        except Exception as e:
            logger.warning(f"Transformer-based semantic similarity failed: {e}. Falling back to TF-IDF.")
    
    # Fallback: Simple TF-IDF-like similarity
    return _tfidf_similarity_fallback(rule_text, document_text)


def _tfidf_similarity_fallback(text1: str, text2: str) -> float:
    """
    Simple fallback similarity using term overlap.
    
    If sentence-transformers is unavailable, use keyword-based similarity.
    """
    if not text1 or not text2:
        return 0.0
    
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    # Jaccard similarity
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    jaccard_sim = intersection / union if union > 0 else 0.0
    
    return float(jaccard_sim)


# Export public API
# --- BiLSTM Classifier (optional, requires PyTorch) ---
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset
    _HAS_TORCH = True
except Exception:
    torch = None  # type: ignore
    nn = None  # type: ignore
    DataLoader = None  # type: ignore
    Dataset = object  # type: ignore
    _HAS_TORCH = False


class _TextDataset(Dataset):
    def __init__(self, sequences, labels):
        self.sequences = sequences
        self.labels = labels

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        return self.sequences[idx], self.labels[idx]


class _BiLSTMModel(nn.Module if _HAS_TORCH else object):
    """Module-level BiLSTM model so joblib can pickle it."""

    def __init__(self, vocab_size, emb_dim, hid_dim, num_layers, n_classes):
        if not _HAS_TORCH:
            raise RuntimeError("PyTorch required")
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, emb_dim, padding_idx=0)
        self.lstm = nn.LSTM(emb_dim, hid_dim, num_layers=num_layers, bidirectional=True, batch_first=True)
        self.head = nn.Linear(hid_dim * 2, n_classes)

    def forward(self, x):
        emb = self.embedding(x)
        out, _ = self.lstm(emb)
        pooled = out.mean(dim=1)
        return self.head(pooled)


class BiLSTMClassifier:
    """Simple BiLSTM classifier with a small vocabulary builder.

    Note: This is a compact prototype for experimenting with sequence models.
    It is intentionally minimal: it builds a token->id map from training texts,
    uses an embedding layer, a bidirectional LSTM and a linear head.
    Requires PyTorch to be installed to use.
    """

    def __init__(self, embedding_dim: int = 128, hidden_dim: int = 128, num_layers: int = 1, max_vocab: int = 20000):
        if not _HAS_TORCH:
            raise RuntimeError("PyTorch required for BiLSTMClassifier")
        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.max_vocab = max_vocab
        self._vocab = {"<pad>": 0, "<unk>": 1}
        self._inv_vocab = None
        self.model = None

    def _tokenize(self, text: str):
        return text.lower().strip().split()

    def _build_vocab(self, texts):
        freq = {}
        for t in texts:
            for w in self._tokenize(t):
                freq[w] = freq.get(w, 0) + 1
        items = sorted(freq.items(), key=lambda x: -x[1])[: max(0, self.max_vocab - len(self._vocab))]
        for w, _ in items:
            if w not in self._vocab:
                self._vocab[w] = len(self._vocab)
        self._inv_vocab = {i: w for w, i in self._vocab.items()}

    def _texts_to_sequences(self, texts, maxlen: int = None):
        seqs = []
        max_l = 0
        for t in texts:
            s = [self._vocab.get(w, self._vocab["<unk>"]) for w in self._tokenize(t)]
            seqs.append(s)
            if len(s) > max_l:
                max_l = len(s)
        if maxlen is None:
            maxlen = max(1, max_l)
        padded = [s[:maxlen] + [0] * max(0, maxlen - len(s)) for s in seqs]
        return padded, maxlen

    def fit(self, texts, labels, epochs: int = 5, batch_size: int = 32, lr: float = 1e-3):
        self._build_vocab(texts)
        sequences, maxlen = self._texts_to_sequences(texts)
        X = torch.tensor(sequences, dtype=torch.long)
        y = torch.tensor(labels, dtype=torch.long)

        n_classes = int(max(y).item() + 1) if y.numel() > 0 else 2
        vocab_size = len(self._vocab)
        self.model = _BiLSTMModel(vocab_size, self.embedding_dim, self.hidden_dim, self.num_layers, n_classes)

        ds = _TextDataset(X, y)
        dl = DataLoader(ds, batch_size=batch_size, shuffle=True)

        opt = torch.optim.Adam(self.model.parameters(), lr=lr)
        loss_fn = nn.CrossEntropyLoss()

        self.model.train()
        for epoch in range(epochs):
            total_loss = 0.0
            for bx, by in dl:
                opt.zero_grad()
                out = self.model(bx)
                loss = loss_fn(out, by)
                loss.backward()
                opt.step()
                total_loss += loss.item() * bx.size(0)
            avg = total_loss / len(ds)
            print(f"[BiLSTM] Epoch {epoch+1}/{epochs} loss={avg:.4f}")

    def predict_proba(self, texts):
        if self.model is None:
            raise RuntimeError("Model not trained")
        sequences, _ = self._texts_to_sequences(texts)
        X = torch.tensor(sequences, dtype=torch.long)
        self.model.eval()
        with torch.no_grad():
            logits = self.model(X)
            probs = torch.softmax(logits, dim=1).cpu().numpy().tolist()
        return probs

    def predict(self, texts):
        probs = self.predict_proba(texts)
        return [int(max(range(len(p)), key=lambda i: p[i])) for p in probs]


__all__ = [
    'SemanticSimilarityCalculator',
    'compute_semantic_score',
    'SENTENCE_TRANSFORMERS_AVAILABLE',
    'BiLSTMClassifier',
]
