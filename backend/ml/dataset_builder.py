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

import re
import unicodedata
from django.db.models import Q

from api.models import Norme, Document, Validation, Rule, TrainingSample, RuleTrainingSample
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
def _clean_text(value: str) -> str:
    if not value:
        return ''
    text = unicodedata.normalize('NFKC', value)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def sync_training_samples_from_evidence(document_ids=None) -> Dict:
    """Backfill TrainingSample rows from existing RuleTrainingSample evidence.

    This keeps the legacy training dataset table aligned with the evidence
    repository that the dashboard and ML pipeline already use.
    """
    created = 0
    updated = 0
    documents = {}

    evidence_qs = RuleTrainingSample.objects.select_related('document', 'rule', 'norm').all()
    if document_ids is not None:
        evidence_qs = evidence_qs.filter(document_id__in=document_ids)

    for evidence in evidence_qs:
        document = evidence.document
        if not document:
            continue

        bucket = documents.setdefault(document.id, {
            'document': document,
            'features': {},
            'rule_results': {},
            'approved_rules': [],
            'rejected_rules': [],
        })

        rule_name = evidence.rule_title or (getattr(evidence.rule, 'title', '') or f'Rule {evidence.rule_id}')
        label = str(evidence.label or '').strip().lower()
        is_valid = 1 if label == 'approved' else 0 if label == 'rejected' else None

        if is_valid is not None:
            bucket['features'][rule_name] = is_valid
            bucket['rule_results'][rule_name] = is_valid
            if is_valid:
                bucket['approved_rules'].append(rule_name)
            else:
                bucket['rejected_rules'].append(rule_name)

    for document_id, bucket in documents.items():
        document = bucket['document']
        features = bucket['features'] or {}
        total_rules = len(features)
        valid_rules_count = sum(1 for value in features.values() if value == 1)
        invalid_rules_count = total_rules - valid_rules_count
        compliance_score = int(round((valid_rules_count / total_rules) * 100)) if total_rules else 0

        explicit_final_decision = document.final_decision if document.is_finalized else None
        status_source = (
            explicit_final_decision
            if explicit_final_decision and explicit_final_decision != Document.Status.PENDING
            else document.status
        )
        approved_flag = True if status_source in [Document.Status.APPROVED, Document.Status.AUTO_APPROVED] else False if status_source == Document.Status.REJECTED else None

        sample, created_flag = TrainingSample.objects.update_or_create(
            document=document,
            defaults={
                'norm_id': document.norme_id,
                'features': features,
                'feature_vector': features,
                'confidence_score': 0.0,
                'teamlead_decision': status_source,
                'final_decision': status_source,
                'approved': approved_flag,
                'label': status_source,
                'standard': document.norme.name if document.norme else 'ISO9001',
                'total_rules': total_rules,
                'valid_rules_count': valid_rules_count,
                'invalid_rules_count': invalid_rules_count,
                'rule_results_json': bucket['rule_results'],
                'compliance_score': compliance_score,
                'approved_rules': bucket['approved_rules'],
                'rejected_rules': bucket['rejected_rules'],
                'rule_text': '',
                'document_text': '',
                'evidence_text': '',
            },
        )
        if created_flag:
            created += 1
        else:
            updated += 1

    return {
        'success': True,
        'created': created,
        'updated': updated,
        'documents': len(documents),
    }


def buildTrainingDataset(norm_id: int) -> Dict:
    """
    Build a training dataset from the semantic evidence repository.
    This also backfills the legacy TrainingSample table from existing evidence rows.

    Each RuleTrainingSample becomes one training sample for ML training.
   """
    sync_training_samples_from_evidence()

    try:
        norm = Norme.objects.get(pk=norm_id)
    except Norme.DoesNotExist:
        return {
            'success': False,
            'error': f'Norm {norm_id} not found',
            'statistics': {
                'total_samples': 0,
                'approved_count': 0,
                'rejected_count': 0,
                'rules_count': 0,
                'training_enabled': False,
            },
            'samples': [],
        }

    samples_qs = RuleTrainingSample.objects.filter(norm=norm).select_related('rule')
    approved_qs = samples_qs.filter(label='approved')
    rejected_qs = samples_qs.filter(label='rejected')

    seen = set()
    cleaned_samples = []
    for sample in samples_qs:
        text = _clean_text(sample.evidence_text or '')
        if not text:
            continue
        key = (sample.rule_id, text.lower(), sample.label or '')
        if key in seen:
            continue
        seen.add(key)

        cleaned_samples.append({
            'id': sample.id,
            'rule_id': sample.rule_id,
            'rule_name': sample.rule_title or (sample.rule.title if sample.rule_id else ''),
            'evidence_text': text,
            'label': sample.label or 'pending',
            'score': float(sample.confidence_score or sample.semantic_score or 0.0),
            'compliance_score': float(sample.confidence_score or sample.semantic_score or 0.0),
            'norm_id': norm.id,
            'created_at': sample.created_at.isoformat() if sample.created_at else None,
            'features': {
                'evidence_length': len(text),
                'semantic_score': float(sample.semantic_score or 0.0),
                'confidence_score': float(sample.confidence_score or 0.0),
                'rule_category': sample.rule_title or '',
            },
        })

    approved_count = sum(1 for item in cleaned_samples if item['label'] == 'approved')
    rejected_count = sum(1 for item in cleaned_samples if item['label'] == 'rejected')
    total_samples = approved_count + rejected_count

    rule_ids = set(item['rule_id'] for item in cleaned_samples if item['rule_id'])
    rules_count = norm.rules.count()
    coverage_rate = round(len(rule_ids) / max(rules_count, 1) * 100, 1) if rules_count else 0.0

    non_empty = [item['evidence_text'] for item in cleaned_samples]
    unique_texts = set(non_empty)
    duplicate_rate = round((1 - len(unique_texts) / max(len(non_empty), 1)) * 100, 1) if non_empty else 0.0
    avg_length = round(sum(len(t.split()) for t in non_empty) / max(len(non_empty), 1), 1) if non_empty else 0.0

    if total_samples > 0:
        minority = min(approved_count, rejected_count)
        class_balance = round(minority / max(total_samples - minority, 1) * 100, 1)
        class_balance = min(class_balance, 100.0)
    else:
        class_balance = 0.0

    richness = round(
        0.35 * min(total_samples / max(rules_count * 10, 1) * 100, 100)
        + 0.25 * class_balance
        + 0.20 * (100 - duplicate_rate)
        + 0.20 * coverage_rate,
        1,
    )

    quality_score = round(
        0.40 * (100 - duplicate_rate)
        + 0.30 * min(avg_length / 50 * 100, 100)
        + 0.30 * class_balance,
        1,
    )

    statistics = {
        'total_samples': total_samples,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'pending_count': sum(1 for item in cleaned_samples if item['label'] == 'pending'),
        'rules_count': rules_count,
        'covered_rules_count': len(rule_ids),
        'coverage_rate': coverage_rate,
        'duplicate_rate': duplicate_rate,
        'avg_evidence_length': avg_length,
        'class_balance': class_balance,
        'dataset_richness': richness,
        'quality_score': quality_score,
        'training_enabled': total_samples >= 20,
        'training_min': 20,
    }

    return {
        'success': True,
        'norm': norm,
        'statistics': statistics,
        'samples': cleaned_samples,
    }


__all__ = [
    'ISO9001DatasetBuilder',
    'generate_iso9001_dataset_simple',
    'buildTrainingDataset',
]
