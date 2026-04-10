from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class Department(models.Model):
    DEPARTMENT_CHOICES = [
        ('DIGITAL', 'Digital Operations'),
        ('AERONAUTIQUE', 'Aeronautics'),
        ('AUTOMOBILE', 'Automobile Production'),
        ('QUALITE', 'Quality Management'),
    ]
    
    code = models.CharField(max_length=50, unique=True, choices=DEPARTMENT_CHOICES)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    theme_color = models.CharField(max_length=7, default='#1976d2')
    
    class Meta:
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Role(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'Administrator'),
        ('TEAMLEAD', 'Team Lead'),
        ('EMPLOYEE', 'Employee'),
    ]
    
    code = models.CharField(max_length=50, unique=True, choices=ROLE_CHOICES)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    keycloak_id = models.CharField(max_length=255, blank=True, null=True)  # Allow null, not unique
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.role.code}"
    
    def clean(self):
        if self.role.code == 'ADMIN' and self.department:
            raise ValidationError("ADMIN role cannot have a department.")
        
        if self.role.code in ['TEAMLEAD', 'EMPLOYEE'] and not self.department:
            raise ValidationError(f"{self.role.code} role must have a department.")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class AuditLog(models.Model):
    """Track changes to user profiles and authentication events"""
    ACTION_CHOICES = [
        ('CREATE', 'User Created'),
        ('UPDATE', 'User Updated'),
        ('DELETE', 'User Deleted'),
        ('LOGIN', 'User Logged In'),
        ('PASSWORD_CHANGE', 'Password Changed'),
        ('ROLE_CHANGE', 'Role Changed'),
        ('DEPARTMENT_CHANGE', 'Department Changed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs_as_target')
    description = models.TextField(blank=True)
    changes = models.JSONField(default=dict, blank=True)  # Store what changed
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.action} by {self.user} at {self.timestamp}"

