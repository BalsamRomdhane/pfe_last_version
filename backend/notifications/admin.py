from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display   = ['id', 'recipient_username', 'notification_type', 'priority', 'title', 'is_read', 'created_at']
    list_filter    = ['notification_type', 'priority', 'is_read']
    search_fields  = ['recipient_username', 'title', 'message']
    ordering       = ['-created_at']
    readonly_fields= ['created_at']

    actions = ['mark_as_read', 'mark_as_unread']

    @admin.action(description='Mark selected as read')
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description='Mark selected as unread')
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
