"""
Dataset builder for ISO 9001 compliance training.

Transforms raw validations into structured training samples with features.

Pipeline:
1. Fetch ISO9001 Norme
2. Collect all Documents + Validations
3. Extract features (version, author, date, etc.)
4. Build training samples
5. Export CSV for ML training
6. Create TrainingSample records
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

from django.db.models import Q

from api.models import Norme, Document, Validation, Rule, TrainingSample
from api.utils import extract_document_text
from ml.feature_engineering import build_feature_vector_from_text, FeatureExtractor

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'


class ISO9001DatasetBuilder:
    """Build training dataset from ISO 9001 validations."""
    
    # ISO 9001 keywords for detection
    ISO9001_KEYWORDS = ['iso9001', 'iso 9001', 'iso-9001', 'document control', 'quality management']
    
    @staticmethod
    def _ensure_data_dir():
        """Ensure data directory exists."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def find_iso9001_norm() -> Optional[Norme]:
        """
        Find existing ISO 9001 norm in database.
        
        Search strategy:
        1. Exact match on name
        2. Contains "iso9001" or "iso 9001"
        3. First norm if none found (might be ISO 9001)
        
        Returns:
            Norme instance or None
        """
        # Strategy 1: Exact match
        norme = Norme.objects.filter(name__iexact='ISO9001').first()
        if norme:
            logger.info(f"Found ISO9001 norm (exact match): {norme.name}")
            return norme
        
        # Strategy 2: Contains keyword
        for keyword in ISO9001DatasetBuilder.ISO9001_KEYWORDS:
            norme = Norme.objects.filter(name__icontains=keyword).first()
            if norme:
                logger.info(f"Found ISO9001 norm (keyword match '{keyword}'): {norme.name}")
                return norme
        
        # Strategy 3: All norms if only one exists
        all_norms = Norme.objects.all()
        if all_norms.count() == 1:
            norme = all_norms.first()
            logger.warning(f"Only one norm in DB, using it: {norme.name}")
            return norme
        
        logger.error("No ISO9001 norm found in database")
        return None
    
    @classmethod
    def build_dataset(cls) -> Dict:
        """
        Build complete dataset from ISO 9001 validations.
        
        Returns:
            {
                'success': bool,
                'norme': Norme or None,
                'documents_count': int,
                'validations_count': int,
                'samples_created': int,
                'samples_updated': int,
                'csv_path': str,
                'statistics': {...},
                'errors': [str],
            }
        """
        cls._ensure_data_dir()
        
        result = {
            'success': False,
            'norme': None,
            'documents_count': 0,
            'validations_count': 0,
            'samples_created': 0,
            'samples_updated': 0,
            'csv_path': None,
            'statistics': {},
            'errors': [],
        }
        
        try:
            # Step 1: Find ISO9001 norm
            norme = cls.find_iso9001_norm()
            if not norme:
                result['errors'].append("ISO9001 norm not found in database")
                logger.error("Failed to find ISO9001 norm")
                return result
            
            result['norme'] = norme
            logger.info(f"Using norm: {norme.name} (ID: {norme.id})")
            
            # Step 2: Collect documents for this norm
            documents = Document.objects.filter(norme=norme).order_by('created_at')
            result['documents_count'] = documents.count()
            logger.info(f"Found {result['documents_count']} documents for {norme.name}")
            
            # Step 3: Build training data
            training_rows = []
            validations_processed = 0
            
            for doc in documents:
                validations = Validation.objects.filter(
                    document=doc
                ).select_related('rule').order_by('rule_id')
                
                if not validations.exists():
                    logger.debug(f"Document {doc.id} has no validations, skipping")
                    continue
                
                # Extract document text once
                document_text = ''
                try:
                    if doc.file:
                        document_text = extract_document_text(doc)[:3000]  # Limit to 3000 chars
                except Exception as e:
                    logger.warning(f"Could not extract text from document {doc.id}: {e}")
                
                # Process each validation
                for validation in validations:
                    try:
                        rule = validation.rule
                        
                        # Build feature vector
                        feature_vector = build_feature_vector_from_text(
                            document_text=document_text,
                            rule_text=rule.title,
                            evidence_text=validation.evidence_text or ''
                        )
                        
                        # Determine label
                        if validation.is_valid is True:
                            label = 1
                        elif validation.is_valid is False:
                            label = 0
                        else:
                            label = None  # Pending validation
                        
                        # Build row
                        row = {
                            'document_id': doc.id,
                            'document_name': f"doc_{doc.id}",
                            'norm_id': norme.id,
                            'norm_name': norme.name,
                            'rule_id': rule.id,
                            'rule_title': rule.title,
                            'rule_description': rule.description or '',
                            'document_text': document_text[:500],  # Truncate for CSV
                            'evidence_text': validation.evidence_text or '',
                            'is_valid': validation.is_valid,
                            'label': label,
                            'features_json': json.dumps(feature_vector),
                            'created_at': validation.updated_at.isoformat(),
                        }
                        
                        training_rows.append(row)
                        validations_processed += 1
                        
                        # Create or update TrainingSample
                        sample, created = TrainingSample.objects.update_or_create(
                            document=doc,
                            defaults={
                                'norm_id': norme.id,
                                'rule_id': rule.id,
                                'rule_text': rule.title,
                                'document_text': document_text,
                                'evidence_text': validation.evidence_text or '',
                                'feature_vector': feature_vector,
                                'label': 'approved' if label == 1 else ('rejected' if label == 0 else 'pending'),
                                'standard': norme.name,
                                'approved': True if label == 1 else (False if label == 0 else None),
                                'teamlead_decision': validation.teamlead_username or '',
                            }
                        )
                        
                        if created:
                            result['samples_created'] += 1
                        else:
                            result['samples_updated'] += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing validation {validation.id}: {e}")
                        result['errors'].append(f"Validation {validation.id}: {str(e)}")
                        continue
            
            result['validations_count'] = validations_processed
            logger.info(f"Processed {validations_processed} validations")
            
            if not training_rows:
                result['errors'].append("No validations found to build dataset")
                logger.warning("No training rows generated")
                return result
            
            # Step 4: Write CSV
            csv_path = DATA_DIR / f'iso9001_dataset.csv'
            try:
                fieldnames = list(training_rows[0].keys())
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(training_rows)
                
                result['csv_path'] = str(csv_path)
                logger.info(f"CSV exported to {csv_path}")
            except Exception as e:
                logger.error(f"Error writing CSV: {e}")
                result['errors'].append(f"CSV write failed: {str(e)}")
                return result
            
            # Step 5: Calculate statistics
            result['statistics'] = cls._calculate_statistics(training_rows)
            
            result['success'] = True
            logger.info("Dataset generation completed successfully")
            
        except Exception as e:
            logger.error(f"Fatal error in dataset building: {e}")
            result['errors'].append(f"Fatal error: {str(e)}")
        
        return result
    
    @staticmethod
    def _calculate_statistics(training_rows: List[Dict]) -> Dict:
        """Calculate dataset statistics."""
        stats = {
            'total_rows': len(training_rows),
            'approved_count': 0,
            'rejected_count': 0,
            'pending_count': 0,
            'label_distribution': {},
            'avg_evidence_length': 0,
            'avg_document_length': 0,
        }
        
        evidence_lengths = []
        doc_lengths = []
        
        for row in training_rows:
            label = row.get('label')
            if label == 1:
                stats['approved_count'] += 1
            elif label == 0:
                stats['rejected_count'] += 1
            else:
                stats['pending_count'] += 1
            
            if row.get('evidence_text'):
                evidence_lengths.append(len(row['evidence_text']))
            
            if row.get('document_text'):
                doc_lengths.append(len(row['document_text']))
        
        if evidence_lengths:
            stats['avg_evidence_length'] = sum(evidence_lengths) // len(evidence_lengths)
        
        if doc_lengths:
            stats['avg_document_length'] = sum(doc_lengths) // len(doc_lengths)
        
        # Label distribution
        stats['label_distribution'] = {
            'approved': stats['approved_count'],
            'rejected': stats['rejected_count'],
            'pending': stats['pending_count'],
        }
        
        return stats


def generate_iso9001_dataset_simple() -> Dict:
    """
    Convenience function to build ISO9001 dataset.
    
    Returns: Result dictionary with status and statistics
    """
    builder = ISO9001DatasetBuilder()
    return builder.build_dataset()


# Export public API
__all__ = [
    'ISO9001DatasetBuilder',
    'generate_iso9001_dataset_simple',
]
