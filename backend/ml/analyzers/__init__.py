"""
Document compliance analysis module.
Performs semantic matching between document content and ISO rules.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sklearn.neighbors import NearestNeighbors

from ..preprocessors import ISOTextPreprocessor
from ..vectorizers import VectorizerManager

logger = logging.getLogger(__name__)


class ComplianceAnalyzer:
    """Analyzes document compliance against ISO standards."""

    def __init__(self, vectorizer_manager: VectorizerManager = None):
        """
        Initialize compliance analyzer.

        Args:
            vectorizer_manager: Vectorizer manager instance
        """
        self.vectorizer_manager = vectorizer_manager or VectorizerManager()
        self.preprocessor = ISOTextPreprocessor()
        self.rules_db = {}  # Cache for rules vectors
        self.similarity_threshold = 0.3  # Minimum similarity for rule detection

    def set_similarity_threshold(self, threshold: float):
        """
        Set similarity threshold for rule detection.

        Args:
            threshold: Similarity threshold (0-1)
        """
        self.similarity_threshold = max(0.0, min(1.0, threshold))

    def load_rules_database(self, standard: str = 'ISO9001') -> Dict[str, Any]:
        """
        Load ISO rules for a specific standard from the database.
        Falls back to RULES_BY_STANDARD if no DB rules found.
        """
        rules_dict = {}

        # Primary: load from actual DB rules for the norm matching `standard`
        try:
            from api.models import Norme
            norm = (
                Norme.objects.filter(name__iexact=standard).first()
                or Norme.objects.filter(name__icontains=standard).first()
            )
            if norm:
                for rule in norm.rules.order_by('id'):
                    rule_id = f"rule_{rule.id}"
                    rules_dict[rule_id] = {
                        'id': rule_id,
                        'db_id': rule.id,
                        'text': f"{rule.title}. {rule.description}".strip(),
                        'title': rule.title,
                        'standard': standard,
                        'vector': None,
                    }
        except Exception as e:
            logger.warning(f"Could not load rules from DB: {e}")

        # Fallback: use RULES_BY_STANDARD static list
        if not rules_dict:
            from api.models import RULES_BY_STANDARD
            # Normalize: try exact, then strip spaces
            key = standard
            if key not in RULES_BY_STANDARD:
                key = standard.replace(' ', '')
            rules = RULES_BY_STANDARD.get(key, [])
            for i, rule_text in enumerate(rules):
                rule_id = f"{standard.lower()}_{i + 1}"
                rules_dict[rule_id] = {
                    'id': rule_id,
                    'text': rule_text,
                    'standard': standard,
                    'vector': None,
                }

        self.rules_db[standard] = rules_dict
        return rules_dict

    def vectorize_rules(self, standard: str = 'ISO9001') -> bool:
        """Compute vector representations for all rules."""
        if standard not in self.rules_db:
            self.load_rules_database(standard)

        rules = self.rules_db.get(standard, {})
        if not rules:
            logger.error("No rules loaded for standard: %s", standard)
            return False

        rule_texts = [rule['text'] for rule in rules.values()]

        # Preprocess rule texts; fall back to raw text if preprocessing yields nothing
        processed_rules = []
        for text in rule_texts:
            try:
                processed = self.preprocessor.preprocess_text(text)
                tokens = processed.get('lemmatized_tokens') or processed.get('tokens') or []
                joined = ' '.join(tokens).strip()
                processed_rules.append(joined if joined else text)
            except Exception:
                processed_rules.append(text)

        # Remove empty strings
        processed_rules = [t if t.strip() else 'unknown' for t in processed_rules]

        if not processed_rules:
            logger.error("No rules to vectorize")
            return False

        try:
            self.vectorizer_manager.fit_tfidf(processed_rules)
            rule_vectors = self.vectorizer_manager.transform_tfidf(processed_rules)

            if rule_vectors is None or len(rule_vectors) == 0:
                logger.error("TF-IDF transform returned empty result")
                return False

            for i, rule_id in enumerate(rules.keys()):
                if i < len(rule_vectors):
                    self.rules_db[standard][rule_id]['vector'] = rule_vectors[i]

            logger.info("Vectorized %d rules for %s", len(rules), standard)
            return True

        except Exception as e:
            logger.error("Error vectorizing rules: %s", e)
            return False

    def analyze_document(self, document_text: str, standard: str = 'ISO9001') -> Dict[str, Any]:
        """
        Analyze document compliance against ISO rules.

        Args:
            document_text: Full text of the document
            standard: ISO standard to check against

        Returns:
            Analysis results dictionary
        """
        try:
            # Preprocess document
            processed_doc = self.preprocessor.preprocess_iso_text(document_text)

            if processed_doc.get('error'):
                return {
                    'standard': standard,
                    'error': processed_doc['error'],
                    'detected_rules': [],
                    'missing_rules': [],
                    'compliance_score': 0,
                    'matches': []
                }

            # Ensure rules are loaded and vectorized
            if standard not in self.rules_db:
                self.load_rules_database(standard)

            # Re-load if the cached entry is empty (e.g. stale singleton state)
            if not self.rules_db.get(standard):
                self.load_rules_database(standard)

            if not any(rule.get('vector') is not None for rule in self.rules_db[standard].values()):
                if not self.vectorize_rules(standard):
                    return {
                        'standard': standard,
                        'error': 'Failed to vectorize rules',
                        'detected_rules': [],
                        'missing_rules': [],
                        'compliance_score': 0,
                        'matches': []
                    }

            # Analyze sentences against rules
            detected_rules = []
            matches = []
            rule_vectors = []

            # Collect rule vectors
            for rule in self.rules_db[standard].values():
                if rule.get('vector') is not None:
                    rule_vectors.append(rule['vector'])

            if not rule_vectors:
                return {
                    'standard': standard,
                    'error': 'No rule vectors available',
                    'detected_rules': [],
                    'missing_rules': [],
                    'compliance_score': 0,
                    'matches': []
                }

            rule_vectors = np.array(rule_vectors)

            # Analyze each sentence
            sentences = processed_doc.get('sentences', [])
            for sentence in sentences:
                sentence_processed = self.preprocessor.preprocess_text(sentence)
                sentence_tokens = sentence_processed.get('lemmatized_tokens', [])

                if not sentence_tokens:
                    continue

                # Vectorize sentence
                sentence_text = ' '.join(sentence_tokens)
                sentence_vector = self.vectorizer_manager.transform_tfidf([sentence_text])

                if sentence_vector is None or len(sentence_vector) == 0:
                    continue

                sentence_vector = sentence_vector[0]

                # Find similar rules
                similar_rules = self.vectorizer_manager.find_similar_documents(
                    sentence_vector, rule_vectors, top_k=3
                )

                for rule_idx, similarity in similar_rules:
                    if similarity >= self.similarity_threshold:
                        rule_id = list(self.rules_db[standard].keys())[rule_idx]
                        rule = self.rules_db[standard][rule_id]

                        if rule_id not in detected_rules:
                            detected_rules.append(rule_id)

                        matches.append({
                            'rule_id': rule_id,
                            'rule_text': rule['text'],
                            'sentence': sentence,
                            'similarity': round(float(similarity), 3)
                        })

            # Determine missing rules
            all_rule_ids = set(self.rules_db[standard].keys())
            detected_set = set(detected_rules)
            missing_rules = list(all_rule_ids - detected_set)

            # Calculate compliance score
            total_rules = len(all_rule_ids)
            if total_rules > 0:
                compliance_score = int((len(detected_rules) / total_rules) * 100)
            else:
                compliance_score = 0

            return {
                'standard': standard,
                'detected_rules': detected_rules,
                'missing_rules': missing_rules,
                'compliance_score': compliance_score,
                'matches': matches,
                'total_sentences_analyzed': len(sentences),
                'error': None
            }

        except Exception as e:
            logger.error(f"Error analyzing document: {e}")
            return {
                'standard': standard,
                'error': str(e),
                'detected_rules': [],
                'missing_rules': [],
                'compliance_score': 0,
                'matches': []
            }

    def get_rule_details(self, rule_id: str, standard: str = 'ISO9001') -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific rule.

        Args:
            rule_id: Rule identifier
            standard: ISO standard

        Returns:
            Rule details or None
        """
        if standard in self.rules_db and rule_id in self.rules_db[standard]:
            return self.rules_db[standard][rule_id]
        return None

    def update_rule_vector(self, rule_id: str, new_text: str, standard: str = 'ISO9001') -> bool:
        """
        Update vector representation for a modified rule.

        Args:
            rule_id: Rule identifier
            new_text: New rule text
            standard: ISO standard

        Returns:
            True if successful, False otherwise
        """
        try:
            if standard not in self.rules_db:
                return False

            if rule_id not in self.rules_db[standard]:
                return False

            # Preprocess new text
            processed = self.preprocessor.preprocess_text(new_text)
            processed_text = ' '.join(processed.get('lemmatized_tokens', []))

            # Vectorize
            vector = self.vectorizer_manager.transform_tfidf([processed_text])
            if vector is not None and len(vector) > 0:
                self.rules_db[standard][rule_id]['text'] = new_text
                self.rules_db[standard][rule_id]['vector'] = vector[0]
                return True

            return False

        except Exception as e:
            logger.error(f"Error updating rule vector: {e}")
            return False