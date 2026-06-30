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
            # ── Trigger security analysis asynchronously on document creation ──
            # run_security_analysis is non-blocking-safe: it catches all
            # exceptions internally and logs warnings, so it cannot break
            # the document creation flow.
            _trigger_security_analysis(instance)
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


def _trigger_security_analysis(document) -> None:
    """
    Trigger a background security analysis when a document is created.

    The analysis is run synchronously in the same request cycle but is
    wrapped in a broad try/except so that any failure is non-fatal.
    In a production environment this should be moved to a Celery task.
    """
    try:
        from services.security_analysis import run_security_analysis
        run_security_analysis(document_id=document.pk, force=False)
    except Exception as exc:
        logger.warning(
            '_trigger_security_analysis: failed for doc #%s: %s',
            document.pk, exc,
        )


def _notify_document_submitted(document):
    """
    Notify the relevant TeamLead(s) when a document is submitted.

    Strategy:
    1. If document.teamlead_username is already set, notify that specific user.
    2. Otherwise, notify all TeamLeads in the document's department.
       This covers the common case where teamlead_username is empty at
       submission time (it gets populated only after a first validation).
    3. If neither approach finds a recipient, log a warning and skip.
    """
    norme = document.norme.name if document.norme else 'N/A'

    # Build a deduplicated list of recipients
    recipients = set()

    if document.teamlead_username:
        recipients.add(document.teamlead_username)
    elif document.employee_department:
        # Notify all TeamLeads in the same department
        try:
            from rbac.models import UserProfile
            tl_profiles = UserProfile.objects.filter(
                role__code='TEAMLEAD',
                department__code=document.employee_department,
            ).select_related('user')
            for p in tl_profiles:
                recipients.add(p.user.username)
        except Exception as exc:
            logger.warning('_notify_document_submitted: could not load TeamLeads: %s', exc)

    if not recipients:
        logger.warning(
            '_notify_document_submitted: no recipient found for document #%s '
            '(department=%s, teamlead=%s)',
            document.pk, document.employee_department, document.teamlead_username,
        )
        return

    for recipient in recipients:
        if Notification.objects.filter(
            recipient_username=recipient,
            notification_type=Notification.NotificationType.DOCUMENT_SUBMITTED,
            related_object_type='Document',
            related_object_id=str(document.pk),
        ).exists():
            continue
        create_notification(
            recipient,
            'New Document Submitted',
            f"{document.employee_username} submitted a document for {norme} standard review.",
            Notification.NotificationType.DOCUMENT_SUBMITTED,
            Notification.Priority.MEDIUM,
            'Document',
            document.pk,
        )


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
    """
    Notify the assigned TeamLead (or all department TeamLeads) that
    a document is under review and requires their attention.
    Uses the same recipient-resolution logic as _notify_document_submitted.
    """
    norme = document.norme.name if document.norme else 'N/A'
    recipients = set()

    if document.teamlead_username:
        recipients.add(document.teamlead_username)
    elif document.employee_department:
        try:
            from rbac.models import UserProfile
            tl_profiles = UserProfile.objects.filter(
                role__code='TEAMLEAD',
                department__code=document.employee_department,
            ).select_related('user')
            for p in tl_profiles:
                recipients.add(p.user.username)
        except Exception as exc:
            logger.warning('_notify_validation_required: could not load TeamLeads: %s', exc)

    for teamlead in recipients:
        if Notification.objects.filter(
            recipient_username=teamlead,
            notification_type=Notification.NotificationType.VALIDATION_REQUIRED,
            related_object_type='Document',
            related_object_id=str(document.pk),
            is_read=False,
        ).exists():
            continue
        create_notification(
            teamlead,
            'Validation Required',
            f"Document from {document.employee_username} for {norme} requires validation.",
            Notification.NotificationType.VALIDATION_REQUIRED,
            Notification.Priority.HIGH,
            'Document',
            document.pk,
        )


@receiver(post_save, sender='api.TrainingJob')
def on_training_job_saved(sender, instance, **kwargs):
    try:
        if instance.drift_score is None or instance.drift_score < DRIFT_ALERT_THRESHOLD:
            return
        if Notification.objects.filter(notification_type=Notification.NotificationType.ML_DRIFT,
            related_object_type='TrainingJob', related_object_id=str(instance.pk)).exists():
            return

        # Notify all ADMIN users instead of hardcoding 'admin'
        from rbac.models import UserProfile
        admin_profiles = UserProfile.objects.filter(
            role__code='ADMIN'
        ).select_related('user')

        notified = False
        for profile in admin_profiles:
            create_notification(
                profile.user.username,
                'ML Model Drift Detected',
                f"Training job #{instance.pk} for {instance.standard or '?'} "
                f"detected drift score {instance.drift_score:.2f}.",
                Notification.NotificationType.ML_DRIFT,
                Notification.Priority.HIGH,
                'TrainingJob',
                instance.pk,
            )
            notified = True

        # Fallback: if no admin profiles exist, notify 'admin' (legacy behaviour)
        if not notified:
            create_notification(
                'admin',
                'ML Model Drift Detected',
                f"Training job #{instance.pk} for {instance.standard or '?'} "
                f"detected drift score {instance.drift_score:.2f}.",
                Notification.NotificationType.ML_DRIFT,
                Notification.Priority.HIGH,
                'TrainingJob',
                instance.pk,
            )
    except Exception as exc:
        logger.error("Notification signal error on TrainingJob save (id=%s): %s", instance.pk, exc)
