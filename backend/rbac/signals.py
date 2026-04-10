from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile, AuditLog
import json


@receiver(pre_save, sender=UserProfile)
def track_userprofile_changes(sender, instance, **kwargs):
    """Track changes to UserProfile before saving"""
    if instance.id:
        try:
            old_instance = UserProfile.objects.get(id=instance.id)
            changes = {}
            
            # Check for role changes
            if old_instance.role != instance.role:
                changes['role'] = {
                    'old': old_instance.role.code,
                    'new': instance.role.code,
                }
            
            # Check for department changes
            if old_instance.department != instance.department:
                changes['department'] = {
                    'old': old_instance.department.code if old_instance.department else None,
                    'new': instance.department.code if instance.department else None,
                }
            
            # Store changes in the instance for post_save
            instance._audit_changes = changes
        except UserProfile.DoesNotExist:
            instance._audit_changes = {}


@receiver(post_save, sender=UserProfile)
def log_userprofile_changes(sender, instance, created, **kwargs):
    """Log UserProfile creation and changes"""
    user = instance.user
    
    if created:
        # Log user creation
        AuditLog.objects.create(
            user=user,
            action='CREATE',
            target_user=user,
            description=f"User created with role {instance.role.code}",
            changes={
                'role': instance.role.code,
                'department': instance.department.code if instance.department else None,
            }
        )
    else:
        # Log changes if any
        changes = getattr(instance, '_audit_changes', {})
        if changes:
            for change_type, values in changes.items():
                if change_type == 'role':
                    action = 'ROLE_CHANGE'
                    description = f"Role changed from {values['old']} to {values['new']}"
                elif change_type == 'department':
                    action = 'DEPARTMENT_CHANGE'
                    description = f"Department changed from {values['old']} to {values['new']}"
                else:
                    continue
                
                AuditLog.objects.create(
                    user=user,
                    action=action,
                    target_user=user,
                    description=description,
                    changes={change_type: values}
                )


@receiver(post_delete, sender=User)
def log_user_deletion(sender, instance, **kwargs):
    """Log user deletion"""
    # Note: We'll use a pre_delete signal if we need the actual UserProfile info
    AuditLog.objects.create(
        action='DELETE',
        target_user=None,  # User is already deleted
        description=f"User deleted: {instance.username}",
    )


def log_user_action(user, action, description, target_user=None, changes=None, ip_address=None):
    """Helper function to manually log user actions"""
    AuditLog.objects.create(
        user=user,
        action=action,
        target_user=target_user,
        description=description,
        changes=changes or {},
        ip_address=ip_address,
    )
