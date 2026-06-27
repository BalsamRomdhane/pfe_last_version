"""
ASGI config for enterprise_platform project.

Exposes the ASGI callable as a module-level variable named ``application``.
Supports both HTTP (via Django) and WebSocket (via Django Channels).
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')

# django.setup() MUST be called before importing any app-level modules
# (consumers, routing, models…). Without this, apps are not loaded and
# the URLRouter silently 404s on every WebSocket handshake.
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from notifications.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    # Standard Django HTTP handler
    'http': get_asgi_application(),
    # WebSocket handler — JWT auth is validated inside the consumer
    # (query-string token), so AuthMiddlewareStack is kept for session/cookie
    # fallback but is not strictly required.
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
