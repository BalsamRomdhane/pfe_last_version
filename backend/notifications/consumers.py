"""
consumers.py — Django Channels WebSocket consumer for push notifications.

JWT validation is delegated to authentication.jwt_utils.decode_token().
SonarQube S5659: signature is always verified — see jwt_utils.py for details.
"""
import json
import logging

import jwt
from authentication.jwt_utils import decode_token

logger = logging.getLogger(__name__)


def _authenticate_ws_token(token: str) -> str:
    """
    Validate a JWT received on the WebSocket query-string and return the username.

    Returns an empty string on any validation failure (expired, bad signature,
    unknown algorithm, etc.) so the caller can close the connection cleanly
    without leaking error details over the WebSocket.

    Delegates to decode_token() which:
      - Always verifies the signature (HS256 or RS256)
      - Verifies exp / nbf / iat
      - Prevents algorithm confusion attacks
      - Is the single, auditable JWT validation implementation
    """
    if not token:
        return ''
    try:
        payload = decode_token(token)
        return payload.get('preferred_username') or payload.get('sub') or ''
    except jwt.ExpiredSignatureError:
        logger.debug('WebSocket JWT expired')
        return ''
    except (jwt.InvalidTokenError, ValueError) as exc:
        logger.debug('WebSocket JWT invalid: %s', exc)
        return ''


try:
    from channels.generic.websocket import AsyncWebsocketConsumer

    class NotificationConsumer(AsyncWebsocketConsumer):
        """
        WebSocket consumer that delivers real-time notifications.

        Authentication flow:
          1. The client sends the JWT as a query-string parameter (?token=…).
          2. _authenticate_ws_token() validates the signature and claims via
             jwt_utils.decode_token() — signature is ALWAYS verified.
          3. On failure the connection is closed with code 4001 (Unauthorized).
        """

        async def connect(self):
            token    = self._extract_token()
            username = _authenticate_ws_token(token)
            if not username:
                await self.close(code=4001)
                return

            self.username   = username
            self.group_name = f'notifications_{username}'
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            logger.info('WebSocket connected: user=%s', username)

        async def disconnect(self, close_code):
            if hasattr(self, 'group_name'):
                await self.channel_layer.group_discard(
                    self.group_name, self.channel_name
                )

        async def receive(self, text_data=None, bytes_data=None):
            if text_data:
                try:
                    data = json.loads(text_data)
                    if data.get('type') == 'ping':
                        await self.send(text_data=json.dumps({'type': 'pong'}))
                except json.JSONDecodeError:
                    pass

        async def notification_message(self, event):
            await self.send(
                text_data=json.dumps({
                    'type':         'notification',
                    'notification': event['notification'],
                })
            )

        # ── Private helpers ───────────────────────────────────────────────────

        def _extract_token(self) -> str:
            """Parse the token from the WebSocket query-string."""
            qs     = self.scope.get('query_string', b'').decode()
            params = {
                k: v
                for k, v in (
                    p.split('=', 1)
                    for p in qs.split('&')
                    if '=' in p
                )
            }
            return params.get('token', '')

except ImportError:
    # channels is optional; provide a no-op class when it is not installed.
    class NotificationConsumer:  # type: ignore[no-redef]
        pass
