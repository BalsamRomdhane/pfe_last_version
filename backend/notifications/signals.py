import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Notification, create_notification

logger = logging.getLogger(__name__)
COVERAGE_GAP_THRESHOLD = 70.0
DRIFT_ALERT_THRESHOLD  = 0.3


@receiver(post_save, sender='api.Document')
def on_document_saved(sender, instance, created, update_fields=None, **kwargs):
    try:
        from api.models import Document
        if (not created and update_fields is not None and set(update_fields) == {'status'}):
            return
        if created:
            _notify_document_submitted(instance)
            return
        final = instance.final_decision
        if instance.is_finalized and final in (Document.Status.APPROVED, Document.Status.AUTO_APPROVED):
            _notify_document_approved(instance)
        elif instance.is_finalized and final == Document.Status.REJECTED:
            _notify_document_rejected(instance)
        elif instance.status == Document.Status.REVIEWING:
            _notify_validation_required(instance)
    except Exception as exc:
        logger.error("Notification signal error on Document save (id=%s): %s", instance.pk, exc)


def _notify_document_submitted(document):
    teamlead = document.teamlead_username
    if not teamlead:
        return
    if Notification.objects.filter(recipient_username=teamlead,
        notification_type=Notification.NotificationType.DOCUMENT_SUBMITTED,
        related_object_type='Document', related_object_id=str(document.pk)).exists():
        return
    norme = document.norme.name if document.norme else 'N/A'
    create_notification(teamlead, 'New Document Submitted',
        f"{document.employee_username} submitted a document for {norme} standard review.",
        Notification.NotificationType.DOCUMENT_SUBMITTED, Notification.Priority.MEDIUM,
        'Document', document.pk)


def _notify_document_approved(document):
    employee = document.employee_username
    if Notification.objects.filter(recipient_username=employee,
        notification_type=Notification.NotificationType.DOCUMENT_APPROVED,
        related_object_type='Document', related_object_id=str(document.pk)).exists():
        return
    norme = document.norme.name if document.norme else 'N/A'
    create_notification(employee, 'Document Approved',
        f"Your document for {norme} has been approved.",
        Notification.NotificationType.DOCUMENT_APPROVED, Notification.Priority.MEDIUM,
        'Document', document.pk)


def _notify_document_rejected(document):
    employee = document.employee_username
    if Notification.objects.filter(recipient_username=employee,
        notification_type=Notification.NotificationType.DOCUMENT_REJECTED,
        related_object_type='Document', related_object_id=str(document.pk)).exists():
        return
    norme  = document.norme.name if document.norme else 'N/A'
    reason = document.decision_reason or document.reviewer_comment or 'No reason provided.'
    create_notification(employee, 'Document Rejected',
        f"Your document for {norme} was rejected. Reason: {reason[:200]}",
        Notification.NotificationType.DOCUMENT_REJECTED, Notification.Priority.HIGH,
        'Document', document.pk)


def _notify_validation_required(document):
    teamlead = document.teamlead_username
    if not teamlead:
        return
    if Notification.objects.filter(recipient_username=teamlead,
        notification_type=Notification.NotificationType.VALIDATION_REQUIRED,
        related_object_type='Document', related_object_id=str(document.pk), is_read=False).exists():
        return
    norme = document.norme.name if document.norme else 'N/A'
    create_notification(teamlead, 'Validation Required',
        f"Document from {document.employee_username} for {norme} requires validation.",
        Notification.NotificationType.VALIDATION_REQUIRED, Notification.Priority.HIGH,
        'Document', document.pk)


@receiver(post_save, sender='api.TrainingJob')
def on_training_job_saved(sender, instance, **kwargs):
    try:
        if instance.drift_score is None or instance.drift_score < DRIFT_ALERT_THRESHOLD:
            return
        if Notification.objects.filter(notification_type=Notification.NotificationType.ML_DRIFT,
            related_object_type='TrainingJob', related_object_id=str(instance.pk)).exists():
            return
        create_notification('admin', 'ML Model Drift Detected',
            f"Training job #{instance.pk} for {instance.standard or '?'} detected drift score {instance.drift_score:.2f}.",
            Notification.NotificationType.ML_DRIFT, Notification.Priority.HIGH,
            'TrainingJob', instance.pk)
    except Exception as exc:
        logger.error("Notification signal error on TrainingJob save (id=%s): %s", instance.pk, exc)
