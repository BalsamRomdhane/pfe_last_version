import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Notification

logger = logging.getLogger(__name__)


def _username(request):
    return getattr(request.user, 'username', '') or ''


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_notifications(request):
    username = _username(request)
    if not username:
        return Response({'count': 0, 'unread_count': 0, 'results': []})
    try:
        limit = min(int(request.query_params.get('limit', 50)), 200)
    except (ValueError, TypeError):
        limit = 50
    qs = Notification.objects.filter(recipient_username=username).order_by('-created_at')[:limit]
    unread = Notification.objects.filter(recipient_username=username, is_read=False).count()
    from .serializers import NotificationSerializer
    return Response({'count': len(list(qs)), 'unread_count': unread,
                     'results': NotificationSerializer(qs, many=True).data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_unread_notifications(request):
    username = _username(request)
    if not username:
        return Response({'count': 0, 'unread_count': 0, 'results': []})
    qs = Notification.objects.filter(recipient_username=username, is_read=False).order_by('-created_at')
    from .serializers import NotificationSerializer
    data = NotificationSerializer(qs, many=True).data
    return Response({'count': len(data), 'unread_count': len(data), 'results': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    username = _username(request)
    try:
        n = Notification.objects.get(id=notification_id, recipient_username=username)
    except Notification.DoesNotExist:
        return Response({'detail': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)
    n.is_read = True
    n.save(update_fields=['is_read'])
    from .serializers import NotificationSerializer
    return Response(NotificationSerializer(n).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    username = _username(request)
    if not username:
        return Response({'marked': 0})
    updated = Notification.objects.filter(recipient_username=username, is_read=False).update(is_read=True)
    logger.info("Marked %d notifications as read for user %s", updated, username)
    return Response({'marked': updated})
