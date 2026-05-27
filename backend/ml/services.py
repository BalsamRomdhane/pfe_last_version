"""
Main ML service for document compliance analysis.
Integrates all components of the NLP pipeline.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from django.conf import settings

from .extractors import DocumentExtractor
from .preprocessors import ISOTextPreprocessor
from .vectorizers import VectorizerManager
from .analyzers import ComplianceAnalyzer
from .config import SIMILARITY_THRESHOLDS

logger = logging.getLogger(__name__)


class DocumentComplianceService:
    """Main service for document compliance analysis using classical NLP/ML."""

    def __init__(self):
        """Initialize the compliance service."""
        self.extractor = DocumentExtractor()
        self.preprocessor = ISOTextPreprocessor()
        self.vectorizer = VectorizerManager()
        self.analyzer = ComplianceAnalyzer(self.vectorizer)

        # Set default similarity threshold
        default_threshold = SIMILARITY_THRESHOLDS.get('default', 0.4)
        self.analyzer.set_similarity_threshold(default_threshold)

    def analyze_document_file(self, file_path: str, standard: str = 'ISO9001') -> Dict[str, Any]:
        """Analyze a document file for compliance."""
        try:
            document_text = self.extractor.extract_text(file_path)
            if not document_text:
                return {
                    'standard': standard,
                    'error': 'Failed to extract text from document',
                    'detected_rules': [],
                    'missing_rules': [],
                    'compliance_score': 0,
                    'matches': []
                }

            result = self.analyze_document_text(document_text, standard)

            result['file_info'] = {
                'file_path': file_path,
                'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                'text_length': len(document_text)
            }
            return result

        except Exception as e:
            logger.error(f"Error analyzing document file: {e}")
            return {
                'standard': standard,
                'error': str(e),
                'detected_rules': [],
                'missing_rules': [],
                'compliance_score': 0,
                'matches': []
            }

    def analyze_document_text(self, document_text: str, standard: str = 'ISO9001') -> Dict[str, Any]:
        """Analyze document text directly for compliance."""
        # Reset cached rule vectors so they are re-loaded from DB on each call.
        if standard in self.analyzer.rules_db:
            del self.analyzer.rules_db[standard]
        self.analyzer.vectorizer_manager.tfidf_vectorizer = None

        threshold = SIMILARITY_THRESHOLDS.get(standard, SIMILARITY_THRESHOLDS['default'])
        self.analyzer.set_similarity_threshold(threshold)
        return self.analyzer.analyze_document(document_text, standard)

    def get_supported_standards(self) -> List[str]:
        """
        Get list of supported ISO standards.

        Returns:
            List of standard names
        """
        from api.models import RULES_BY_STANDARD
        return list(RULES_BY_STANDARD.keys())

    def get_standard_rules(self, standard: str) -> Dict[str, Any]:
        """
        Get rules for a specific standard.

        Args:
            standard: ISO standard name

        Returns:
            Dictionary of rules
        """
        return self.analyzer.load_rules_database(standard)

    def update_similarity_threshold(self, threshold: float, standard: str = None) -> bool:
        """
        Update the similarity threshold for compliance detection.

        Args:
            threshold: New threshold value (0-1)
            standard: Specific standard, or None for global default

        Returns:
            True if updated successfully
        """
        try:
            if standard:
                # Update for specific standard
                SIMILARITY_THRESHOLDS[standard] = threshold
            else:
                # Update global default
                SIMILARITY_THRESHOLDS['default'] = threshold
                self.analyzer.set_similarity_threshold(threshold)
            return True
        except Exception as e:
            logger.error(f"Error updating threshold: {e}")
            return False

    def retrain_models(self, standard: str = 'ISO9001') -> Dict[str, Any]:
        """
        Retrain compliance analysis models for a standard.

        Args:
            standard: ISO standard to retrain for

        Returns:
            Training results
        """
        try:
            success = self.analyzer.vectorize_rules(standard)
            return {
                'success': success,
                'standard': standard,
                'message': 'Models retrained successfully' if success else 'Failed to retrain models'
            }
        except Exception as e:
            logger.error(f"Error retraining models: {e}")
            return {
                'success': False,
                'standard': standard,
                'message': str(e)
            }

    def get_service_status(self) -> Dict[str, Any]:
        """
        Get current service status and configuration.

        Returns:
            Service status information
        """
        return {
            'service': 'DocumentComplianceService',
            'status': 'active',
            'supported_standards': self.get_supported_standards(),
            'similarity_thresholds': SIMILARITY_THRESHOLDS.copy(),
            'current_threshold': self.analyzer.similarity_threshold,
            'vectorizer_loaded': self.vectorizer.tfidf_vectorizer is not None,
            'models_dir': self.vectorizer.models_dir
        }


# Global service instance
compliance_service = DocumentComplianceService()
