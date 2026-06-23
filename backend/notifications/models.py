from django.db import models


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        DOCUMENT_SUBMITTED  = 'DOCUMENT_SUBMITTED',  'Document Submitted'
        DOCUMENT_APPROVED   = 'DOCUMENT_APPROVED',   'Document Approved'
        DOCUMENT_REJECTED   = 'DOCUMENT_REJECTED',   'Document Rejected'
        VALIDATION_REQUIRED = 'VALIDATION_REQUIRED', 'Validation Required'
        AUDIT_DEADLINE      = 'AUDIT_DEADLINE',      'Audit Deadline Approaching'
        COMPLIANCE_GAP      = 'COMPLIANCE_GAP',      'Compliance Gap Detected'
        CRITICAL_RISK       = 'CRITICAL_RISK',       'Critical Risk Detected'
        ML_DRIFT            = 'ML_DRIFT',            'ML Model Drift Detected'
        REVIEW_OVERDUE      = 'REVIEW_OVERDUE',      'Review Overdue'
        GENERAL             = 'GENERAL',             'General'

    class Priority(models.TextChoices):
        LOW      = 'LOW',      'Low'
        MEDIUM   = 'MEDIUM',   'Medium'
        HIGH     = 'HIGH',     'High'
        CRITICAL = 'CRITICAL', 'Critical'

    recipient_username  = models.CharField(max_length=150, db_index=True)
    title               = models.CharField(max_length=255)
    message             = models.TextField()
    notification_type   = models.CharField(max_length=32, choices=NotificationType.choices,
                                           default=NotificationType.GENERAL, db_index=True)
    priority            = models.CharField(max_length=12, choices=Priority.choices,
                                           default=Priority.MEDIUM, db_index=True)
    is_read             = models.BooleanField(default=False, db_index=True)
    created_at          = models.DateTimeField(auto_now_add=True, db_index=True)
    related_object_type = models.CharField(max_length=64, blank=True, default='')
    related_object_id   = models.CharField(max_length=64, blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        indexes = [
            models.Index(fields=['recipient_username', '-created_at']),
            models.Index(fields=['recipient_username', 'is_read', '-created_at']),
        ]

    def __str__(self):
        s = '(read)' if self.is_read else '(unread)'
        return f"[{self.notification_type}] {self.title} → {self.recipient_username} {s}"


def create_notification(recipient_username, title, message,
                         notification_type=Notification.NotificationType.GENERAL,
                         priority=Notification.Priority.MEDIUM,
                         related_object_type='', related_object_id=''):
    n = Notification.objects.create(
        recipient_username=recipient_username, title=title, message=message,
        notification_type=notification_type, priority=priority,
        related_object_type=related_object_type, related_object_id=str(related_object_id),
    )
    _push_ws_notification(n)
    return n


def _push_ws_notification(notification):
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            f"notifications_{notification.recipient_username}",
            {
                'type': 'notification_message',
                'notification': {
                    'id': notification.id, 'title': notification.title,
                    'message': notification.message,
                    'notification_type': notification.notification_type,
                    'priority': notification.priority, 'is_read': notification.is_read,
                    'created_at': notification.created_at.isoformat(),
                    'related_object_type': notification.related_object_type,
                    'related_object_id': notification.related_object_id,
                },
            }
        )
    except Exception:
        pass
