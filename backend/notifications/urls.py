from django.urls import path
from . import views

urlpatterns = [
    path('',                          views.list_notifications,          name='notifications-list'),
    path('unread/',                   views.list_unread_notifications,   name='notifications-unread'),
    path('read-all/',                 views.mark_all_notifications_read, name='notifications-read-all'),
    path('<int:notification_id>/read/', views.mark_notification_read,    name='notification-read'),
]
