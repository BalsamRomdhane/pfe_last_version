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
    """Module-level BiLSTM model so joblib can pickle it.

    Architecture with regularisation to prevent memorisation:
    - Embedding dropout (drops entire token embeddings)
    - BiLSTM with dropout between layers
    - Layer normalisation on pooled output
    - Two-layer head with intermediate dropout
    """

    def __init__(self, vocab_size, emb_dim, hid_dim, num_layers, n_classes, dropout=0.4):
        if not _HAS_TORCH:
            raise RuntimeError("PyTorch required")
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, emb_dim, padding_idx=0)
        self.emb_dropout = nn.Dropout(dropout)
        self.lstm = nn.LSTM(
            emb_dim, hid_dim,
            num_layers=num_layers,
            bidirectional=True,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.layer_norm = nn.LayerNorm(hid_dim * 2)
        self.head = nn.Sequential(
            nn.Linear(hid_dim * 2, hid_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hid_dim, n_classes),
        )

    def forward(self, x):
        emb = self.emb_dropout(self.embedding(x))
        out, _ = self.lstm(emb)
        # Mean-pool over the sequence dimension
        pooled = out.mean(dim=1)
        pooled = self.layer_norm(pooled)
        return self.head(pooled)


class BiLSTMClassifier:
    """BiLSTM classifier with vocabulary builder, dropout regularisation and early stopping.

    Design principles to prevent inflated (100%) metrics:
    1. Dropout (emb + LSTM + head) — forces the model to learn robust patterns
       rather than memorising training sequences.
    2. Weight decay (L2) via AdamW — penalises large weights.
    3. Early stopping on validation loss — halts training before over-fitting.
    4. The caller (train_models.py) is responsible for GroupShuffleSplit so that
       no document appears in both train and test sets.

    Requires PyTorch to be installed.
    """

    def __init__(
        self,
        embedding_dim: int = 128,
        hidden_dim: int = 128,
        num_layers: int = 1,
        max_vocab: int = 20000,
        dropout: float = 0.4,
        weight_decay: float = 1e-4,
        patience: int = 3,
    ):
        if not _HAS_TORCH:
            raise RuntimeError("PyTorch required for BiLSTMClassifier")
        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.max_vocab = max_vocab
        self.dropout = dropout
        self.weight_decay = weight_decay
        self.patience = patience
        self._vocab = {"<pad>": 0, "<unk>": 1}
        self._inv_vocab = None
        self.model = None
        self._maxlen = None

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
        # Clamp to stored maxlen if model already trained (inference)
        if self._maxlen is not None:
            maxlen = self._maxlen
        padded = [s[:maxlen] + [0] * max(0, maxlen - len(s)) for s in seqs]
        return padded, maxlen

    def fit(self, texts, labels, epochs: int = 10, batch_size: int = 32, lr: float = 1e-3,
            val_split: float = 0.15):
        """Train with:
        - AdamW (weight decay = L2 regularisation)
        - Dropout enforced during training (model.train())
        - Validation-based early stopping (patience=self.patience)
        - Best-weight restore after early stopping
        """
        import math
        self._build_vocab(texts)
        sequences, maxlen = self._texts_to_sequences(texts)
        self._maxlen = maxlen

        # ── Validation split (stratified by label) ───────────────────────────
        from sklearn.model_selection import train_test_split as _tts
        labels_arr = list(labels)
        # Only stratify when both classes are present
        unique_lbls = set(labels_arr)
        if len(unique_lbls) >= 2 and val_split > 0 and len(texts) >= 20:
            idx_tr, idx_val = _tts(
                list(range(len(sequences))),
                test_size=val_split,
                stratify=labels_arr,
                random_state=42,
            )
        else:
            idx_tr = list(range(len(sequences)))
            idx_val = []

        X_tr = torch.tensor([sequences[i] for i in idx_tr], dtype=torch.long)
        y_tr = torch.tensor([labels_arr[i] for i in idx_tr], dtype=torch.long)

        n_classes = int(y_tr.max().item() + 1) if y_tr.numel() > 0 else 2
        vocab_size = len(self._vocab)
        self.model = _BiLSTMModel(
            vocab_size, self.embedding_dim, self.hidden_dim,
            self.num_layers, n_classes, dropout=self.dropout,
        )

        ds_tr = _TextDataset(X_tr, y_tr)
        dl_tr = DataLoader(ds_tr, batch_size=batch_size, shuffle=True)

        # Validation tensors (may be empty)
        has_val = len(idx_val) > 0
        if has_val:
            X_val_t = torch.tensor([sequences[i] for i in idx_val], dtype=torch.long)
            y_val_t = torch.tensor([labels_arr[i] for i in idx_val], dtype=torch.long)

        opt = torch.optim.AdamW(
            self.model.parameters(), lr=lr, weight_decay=self.weight_decay
        )
        loss_fn = nn.CrossEntropyLoss()

        best_val_loss = math.inf
        best_state = None
        no_improve = 0

        for epoch in range(epochs):
            # ── Train ────────────────────────────────────────────────────────
            self.model.train()
            train_loss = 0.0
            for bx, by in dl_tr:
                opt.zero_grad()
                out = self.model(bx)
                loss = loss_fn(out, by)
                loss.backward()
                # Gradient clipping prevents exploding gradients
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=5.0)
                opt.step()
                train_loss += loss.item() * bx.size(0)
            train_loss /= len(ds_tr)

            # ── Validation ───────────────────────────────────────────────────
            if has_val:
                self.model.eval()
                with torch.no_grad():
                    val_out = self.model(X_val_t)
                    val_loss = loss_fn(val_out, y_val_t).item()
                print(
                    f"[BiLSTM] Epoch {epoch+1}/{epochs}"
                    f"  train_loss={train_loss:.4f}"
                    f"  val_loss={val_loss:.4f}"
                )
                # Early stopping
                if val_loss < best_val_loss - 1e-4:
                    best_val_loss = val_loss
                    # Deep copy of state dict
                    best_state = {k: v.clone() for k, v in self.model.state_dict().items()}
                    no_improve = 0
                else:
                    no_improve += 1
                    if no_improve >= self.patience:
                        print(f"[BiLSTM] Early stopping at epoch {epoch+1} (patience={self.patience})")
                        break
            else:
                print(f"[BiLSTM] Epoch {epoch+1}/{epochs}  train_loss={train_loss:.4f}")

        # Restore best weights when early stopping fired
        if best_state is not None:
            self.model.load_state_dict(best_state)
        self.model.eval()

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
