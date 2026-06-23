import json
import logging

import jwt
from django.conf import settings
from jwt import PyJWKClient

logger = logging.getLogger(__name__)


def _decode_verified_token(token):
    """Validate JWTs using the local secret for fallback tokens or the realm JWKS for Keycloak tokens."""
    try:
        header = jwt.get_unverified_header(token)
        if header.get('alg') == 'none':
            raise ValueError('Token algorithm is not allowed.')
    except Exception:
        raise ValueError('Invalid token format.')

    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=['HS256'],
            options={'verify_exp': True},
        )
    except jwt.ExpiredSignatureError:
        raise ValueError('Token has expired. Please log in again.')
    except jwt.InvalidTokenError:
        pass

    jwks_url = (
        f"{settings.KEYCLOAK_SERVER_URL.rstrip('/')}/realms/"
        f"{settings.KEYCLOAK_REALM}/protocol/openid-connect/certs"
    )
    try:
        signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=['RS256'],
            options={'verify_exp': True},
        )
    except jwt.ExpiredSignatureError:
        raise ValueError('Token has expired. Please log in again.')
    except Exception as exc:
        raise ValueError(f'Invalid token: {exc}')


try:
    from channels.generic.websocket import AsyncWebsocketConsumer

    class NotificationConsumer(AsyncWebsocketConsumer):
        async def connect(self):
            username = await self._authenticate()
            if not username:
                await self.close(code=4001)
                return
            self.username   = username
            self.group_name = f"notifications_{username}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            logger.info("WebSocket connected: user=%s", username)

        async def disconnect(self, close_code):
            if hasattr(self, 'group_name'):
                await self.channel_layer.group_discard(self.group_name, self.channel_name)

        async def receive(self, text_data=None, bytes_data=None):
            if text_data:
                try:
                    data = json.loads(text_data)
                    if data.get('type') == 'ping':
                        await self.send(text_data=json.dumps({'type': 'pong'}))
                except json.JSONDecodeError:
                    pass

        async def notification_message(self, event):
            await self.send(text_data=json.dumps({'type': 'notification', 'notification': event['notification']}))

        async def _authenticate(self):
            qs = self.scope.get('query_string', b'').decode()
            params = {k: v for k, v in (p.split('=', 1) for p in qs.split('&') if '=' in p)}
            token = params.get('token', '')
            if not token:
                return ''
            try:
                payload = _decode_verified_token(token)
                return payload.get('preferred_username') or payload.get('sub') or ''
            except Exception:
                return ''

except ImportError:
    class NotificationConsumer:  # type: ignore[no-redef]
        pass
