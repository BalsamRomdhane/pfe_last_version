from django.urls import re_path
from .consumers import NotificationConsumer

# The ProtocolTypeRouter passes the full request path (with leading slash)
# to the URLRouter. The frontend connects to:
#   ws://localhost:8000/api/ws/notifications/?token=...
# so the path received here is: /api/ws/notifications/
#
# We also register /ws/notifications/ as a fallback in case the frontend
# is reconfigured to omit the /api prefix.
websocket_urlpatterns = [
    re_path(r'^/api/ws/notifications/$', NotificationConsumer.as_asgi()),
    re_path(r'^/ws/notifications/$',     NotificationConsumer.as_asgi()),
    # Also match without leading slash (some Channels versions strip it)
    re_path(r'^api/ws/notifications/$',  NotificationConsumer.as_asgi()),
    re_path(r'^ws/notifications/$',      NotificationConsumer.as_asgi()),
]
