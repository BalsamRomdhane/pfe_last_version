import jwt
from rest_framework import authentication, exceptions

class KeycloakUser:
    def __init__(self, username=None, roles=None, department=None, token=None):
        self.username = username or ''
        self.roles = roles or []
        self.department = department
        self.token = token

    @property
    def is_authenticated(self):
        return True

class KeycloakAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth = authentication.get_authorization_header(request).split()
        if not auth or auth[0].lower() != b'bearer':
            return None

        if len(auth) == 1:
            raise exceptions.AuthenticationFailed('Invalid authorization header. No credentials provided.')
        if len(auth) > 2:
            raise exceptions.AuthenticationFailed('Invalid authorization header. Token string should not contain spaces.')

        token = auth[1].decode('utf-8')
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
        except Exception as exc:
            raise exceptions.AuthenticationFailed(f'Invalid token: {exc}')

        username = decoded.get('preferred_username') or decoded.get('sub')
        roles = decoded.get('realm_access', {}).get('roles', [])
        department = None
        if decoded.get('attributes'):
            department = decoded['attributes'].get('department', [None])[0]
        if not department and decoded.get('groups'):
            department = decoded['groups'][0]

        user = KeycloakUser(username=username, roles=roles, department=department, token=token)
        return (user, token)