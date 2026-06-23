import jwt
from django.conf import settings
from django.contrib.auth.models import User
from jwt import PyJWKClient
from rest_framework import authentication, exceptions
from rbac.models import UserProfile


def _decode_verified_token(token):
    """Validate JWTs using the local secret for fallback tokens or the realm JWKS for Keycloak tokens."""
    try:
        header = jwt.get_unverified_header(token)
        if header.get('alg') == 'none':
            raise exceptions.AuthenticationFailed('Token algorithm is not allowed.')
    except jwt.InvalidTokenError:
        raise exceptions.AuthenticationFailed('Invalid token format.')
    except Exception:
        raise exceptions.AuthenticationFailed('Invalid token format.')

    # Local/dev fallback tokens are signed with Django's secret key.
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=['HS256'],
            options={'verify_exp': True},
        )
    except jwt.ExpiredSignatureError:
        raise exceptions.AuthenticationFailed('Token has expired. Please log in again.')
    except jwt.InvalidTokenError:
        pass

    # Real Keycloak tokens are RS256-signed; verify them using the realm JWKS.
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
        raise exceptions.AuthenticationFailed('Token has expired. Please log in again.')
    except Exception as exc:
        raise exceptions.AuthenticationFailed(f'Invalid token: {exc}')


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
            decoded = _decode_verified_token(token)
        except Exception as exc:
            raise exceptions.AuthenticationFailed(f'Invalid token: {exc}')

        username = decoded.get('preferred_username') or decoded.get('sub')

        roles = decoded.get('realm_access', {}).get('roles', []) or []
        if not isinstance(roles, list):
            roles = [roles]

        resource_access = decoded.get('resource_access', {})
        if isinstance(resource_access, dict):
            for client_roles in resource_access.values():
                client_role_list = client_roles.get('roles', [])
                if isinstance(client_role_list, list):
                    roles.extend(client_role_list)
                elif client_role_list:
                    roles.append(client_role_list)

        department = None
        attributes = decoded.get('attributes') or {}
        raw_department = attributes.get('department')
        if isinstance(raw_department, list):
            if raw_department:
                department = raw_department[0]
        elif raw_department:
            department = raw_department

        if not department and decoded.get('groups'):
            department = decoded['groups'][0]

        # Fallback to Django profile if Keycloak token does not include roles/department info
        profile_roles = []
        try:
            if username:
                user = User.objects.get(username=username)
                profile = UserProfile.objects.get(user=user)
                if getattr(profile, 'role', None):
                    profile_roles = [profile.role.code]
                if not department and getattr(profile, 'department', None):
                    department = profile.department.code
        except (User.DoesNotExist, UserProfile.DoesNotExist):
            profile_roles = []

        roles.extend(profile_roles)
        roles = list({role for role in roles if role})

        user = KeycloakUser(username=username, roles=roles, department=department, token=token)
        return (user, token)