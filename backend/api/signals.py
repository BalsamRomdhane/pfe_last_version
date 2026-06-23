"""
Signals for training dataset auto-generation and management.

This module handles:
- Auto-creation of TrainingSample when a Validation is created/updated
- Trigger dataset export after team lead validation
- Tracking validation metrics
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
import logging

from .models import (
    Validation,
    TrainingSample,
    Document,
    RuleTrainingSample,
    aggregate_validation_metrics,
    extract_features,
    build_validation_feature_vector,
    create_document_training_sample,
)
from .utils import extract_document_text

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Validation)
@transaction.atomic
def create_training_sample_on_validation(sender, instance, created, update_fields=None, **kwargs):
    """
    Automatically create or update TrainingSample when Validation is created/updated.
    
    This ensures every validation contributes to the training dataset automatically.
    """
    try:
        document = instance.document
        rule = instance.rule
        
        if not document or not rule:
            logger.warning(f"Validation {instance.id} missing document or rule")
            return
        
        # Log incoming validation
        logger.debug(
            "Validation received: id=%s created=%s update_fields=%s is_valid=%s teamlead=%s",
            instance.id,
            created,
            update_fields,
            instance.is_valid,
            instance.teamlead_username,
        )

        # Extract document text if available
        document_text = ''
        try:
            if document.file:
                document_text = extract_document_text(document)[:2000]  # Limit to 2000 chars
        except Exception as e:
            logger.warning(f"Could not extract text from document {document.id}: {e}")
        
        # Determine the resolved document status for training and approval
        status_source = document.final_decision or document.status
        approved_flag = (
            True if status_source in [Document.Status.APPROVED, Document.Status.AUTO_APPROVED]
            else False if status_source == Document.Status.REJECTED
            else None
        )

        # Aggregate all validations for this document into the document-level sample
        metrics = aggregate_validation_metrics(document)
        feature_vector = build_validation_feature_vector(document)
        
        # VALIDATION: total_rules must equal valid + invalid
        assert metrics['total_rules'] == metrics['valid_rules_count'] + metrics['invalid_rules_count'], \
            'Metrics consistency error: total_rules != valid + invalid'
        
        defaults = {
            'norm_id': document.norme_id,
            'features': extract_features(document),
            'feature_vector': feature_vector,
            'label': status_source,
            'standard': document.norme.name if document.norme else 'ISO9001',
            'teamlead_decision': status_source,
            'final_decision': status_source,
            'decision_reason': document.decision_reason,
            'approved': approved_flag,
            'document_text': document_text,
            'total_rules': metrics['total_rules'],
            'valid_rules_count': metrics['valid_rules_count'],
            'invalid_rules_count': metrics['invalid_rules_count'],
            'approved_rules': metrics['approved_rules'],
            'rejected_rules': metrics['rejected_rules'],
            'rule_results_json': metrics['rule_results_json'],
            'compliance_score': metrics['compliance_score'],
        }
        
        logger.debug(
            "Metrics aggregated for doc=%s: total=%d valid=%d invalid=%d compliance=%d%%",
            document.id, metrics['total_rules'], metrics['valid_rules_count'], 
            metrics['invalid_rules_count'], metrics['compliance_score'],
        )

        # Capture previous sample values for diff logging
        prev = None
        prev_vals = {}
        sample_qs = TrainingSample.objects.filter(document=document)
        if sample_qs.exists():
            prev = sample_qs.first()
            for k in ['norm_id', 'label', 'standard', 'teamlead_decision', 'approved', 'total_rules', 'valid_rules_count', 'invalid_rules_count', 'compliance_score']:
                prev_vals[k] = getattr(prev, k, None)

        # Update or create TrainingSample with aggregated values
        sample, created_sample = TrainingSample.objects.update_or_create(
            document=document,
            defaults=defaults
        )

        # Keep the dedicated document-level dataset synchronized as well.
        try:
            create_document_training_sample(document)
        except Exception as e:
            logger.warning(f"Failed to refresh document training sample for document {document.id}: {e}")

        # Also create or update a RuleTrainingSample for this validation (one per document+rule)
        try:
            RuleTrainingSample.objects.update_or_create(
                document=document,
                rule=rule,
                defaults={
                    'norm': document.norme,
                    'rule_title': rule.title or '',
                    'rule_description': rule.description or '',
                    'document_text': document_text,
                    'evidence_text': instance.evidence_text or '',
                    'reviewer_comment': instance.comment or '',
                    'recommendation': rule.action or '',
                    'confidence_score': float(defaults.get('confidence_score') or 0.0),
                    'semantic_score': float(0.0),
                    'label': 'approved' if instance.is_valid else ('rejected' if instance.is_valid is False else 'pending'),
                    'final_document_decision': document.final_decision or document.status,
                }
            )
        except Exception as e:
            logger.error(f"Failed to create/update RuleTrainingSample for Validation {instance.id}: {e}")

        action = "Created" if created_sample else "Updated"
        # Determine what changed (if updated)
        changes = []
        if not created_sample and prev:
            for k, v in defaults.items():
                old = prev_vals.get(k)
                new = v
                if old != new:
                    changes.append(k)

        if created_sample:
            logger.info(
                "Created TrainingSample id=%s for doc=%s rule=%s validations=%d label=%s total_rules=%d compliance=%d%%",
                sample.id,
                document.id,
                rule.title if rule else 'N/A',
                document.validations.count(),
                sample.label,
                sample.total_rules,
                sample.compliance_score,
            )
        else:
            logger.info(
                "Updated TrainingSample id=%s for doc=%s changed_fields=%s total_rules=%d compliance=%d%%",
                sample.id,
                document.id,
                changes if changes else 'none',
                sample.total_rules,
                sample.compliance_score,
            )
        
        # Trigger dataset export after X validations (optional optimization)
        _check_trigger_dataset_export(document.norme)
        
    except Exception as e:
        logger.error(f"Error creating TrainingSample for Validation {instance.id}: {e}")
        raise


@receiver(post_delete, sender=Validation)
def cleanup_training_sample_on_validation_delete(sender, instance, **kwargs):
    """
    Optionally cleanup or archive TrainingSample when Validation is deleted.
    Current behavior: log only (don't delete sample to preserve history).
    """
    try:
        logger.info(f"Validation {instance.id} deleted (TrainingSample preserved for history)")
    except Exception as e:
        logger.error(f"Error handling Validation deletion: {e}")


def _check_trigger_dataset_export(norme):
    """
    Check if we should trigger dataset export after validation.
    Current logic: export after every 10 new validations.
    """
    if not norme:
        return
    
    # Count recent validations (last 1 hour)
    from django.utils import timezone
    from datetime import timedelta
    
    recent_validations = Validation.objects.filter(
        rule__norme=norme,
        updated_at__gte=timezone.now() - timedelta(hours=1)
    ).count()
    
    # Trigger export every 10 validations (can be configured)
    if recent_validations % 10 == 0 and recent_validations > 0:
        logger.info(f"Triggering dataset export for {norme.name} after {recent_validations} validations")
        # Import here to avoid circular dependency
        from .utils_dataset import export_datasets_for_norm
        try:
            export_datasets_for_norm(norme)
            logger.info(f"Dataset export completed for {norme.name}")
        except Exception as e:
            logger.error(f"Dataset export failed for {norme.name}: {e}")
