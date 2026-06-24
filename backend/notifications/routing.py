try:
    from django.urls import re_path
    from .consumers import NotificationConsumer
    websocket_urlpatterns = [
        # The ASGI protocol router handles WebSocket connections at the root level.
        # The frontend connects to /api/ws/notifications/ but Django Channels receives
        # the path after stripping the WS upgrade, so we match both with and without /api prefix.
        re_path(r'^api/ws/notifications/$', NotificationConsumer.as_asgi()),
        re_path(r'^ws/notifications/$', NotificationConsumer.as_asgi()),
    ]
except ImportError:
    websocket_urlpatterns = []
