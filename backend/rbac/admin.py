from django.contrib import admin

from .models import UserProfile, Role, Department, AuditLog


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'department', 'is_first_login', 'created_at', 'updated_at')
    list_filter = ('role', 'department', 'is_first_login')
    search_fields = ('user__username', 'user__email', 'role__code', 'department__code')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('user', 'role', 'department', 'is_first_login', 'keycloak_id', 'date_naissance')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user', 'target_user', 'timestamp')
    list_filter = ('action',)
    search_fields = ('user__username', 'target_user__username', 'description')
    readonly_fields = ('timestamp',)
