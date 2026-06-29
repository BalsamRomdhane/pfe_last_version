"""
authentication.py — DRF custom authentication backend.

Uses jwt_utils.decode_token() as the single source of JWT validation.
SonarQube S5659: signature is always verified — see jwt_utils.py for details.
"""
import logging

import jwt
from django.contrib.auth.models import User
from rest_framework import authentication, exceptions
from rbac.models import UserProfile

from .jwt_utils import decode_token

logger = logging.getLogger(__name__)


class KeycloakUser:
    """
    Lightweight user object returned by KeycloakAuthentication.
    Not a Django User — carries only the claims needed for RBAC.
    """

    def __init__(self, username=None, roles=None, department=None, token=None):
        self.username   = username or ''
        self.roles      = roles or []
        self.department = department
        self.token      = token

    @property
    def is_authenticated(self):
        return True


class KeycloakAuthentication(authentication.BaseAuthentication):
    """
    DRF authentication class that validates Bearer JWTs.

    Supported token types:
      - HS256  Django-issued fallback tokens (signed with SECRET_KEY)
      - RS256  Keycloak tokens       (verified via realm JWKS)

    Both paths are handled by jwt_utils.decode_token() which:
      - Always verifies the signature
      - Always verifies exp / nbf / iat
      - Prevents algorithm confusion attacks
      - Is the single, auditable implementation
    """

    def authenticate(self, request):
        auth = authentication.get_authorization_header(request).split()

        if not auth or auth[0].lower() != b'bearer':
            return None

        if len(auth) == 1:
            raise exceptions.AuthenticationFailed(
                'Invalid Authorization header: no token provided.'
            )
        if len(auth) > 2:
            raise exceptions.AuthenticationFailed(
                'Invalid Authorization header: token must not contain spaces.'
            )

        raw_token = auth[1].decode('utf-8')

        try:
            decoded = decode_token(raw_token)
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed(
                'Token has expired. Please log in again.'
            )
        except (jwt.InvalidTokenError, ValueError) as exc:
            raise exceptions.AuthenticationFailed(f'Invalid token: {exc}')

        username = decoded.get('preferred_username') or decoded.get('sub')

        # ── Extract roles ────────────────────────────────────────────────────
        roles: list = decoded.get('realm_access', {}).get('roles', []) or []
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

        # ── Extract department ───────────────────────────────────────────────
        department = None
        attributes  = decoded.get('attributes') or {}
        raw_dept    = attributes.get('department')
        if isinstance(raw_dept, list):
            if raw_dept:
                department = raw_dept[0]
        elif raw_dept:
            department = raw_dept

        if not department and decoded.get('groups'):
            department = decoded['groups'][0]

        # ── Fallback to Django UserProfile ───────────────────────────────────
        # Keycloak tokens may not carry role/department claims when the
        # realm mapper is not configured. Fall back to the Django profile.
        profile_roles: list = []
        try:
            if username:
                user    = User.objects.get(username=username)
                profile = UserProfile.objects.get(user=user)
                if getattr(profile, 'role', None):
                    profile_roles = [profile.role.code]
                if not department and getattr(profile, 'department', None):
                    department = profile.department.code
        except (User.DoesNotExist, UserProfile.DoesNotExist):
            pass

        roles.extend(profile_roles)
        roles = list({r for r in roles if r})   # deduplicate

        keycloak_user = KeycloakUser(
            username=username,
            roles=roles,
            department=department,
            token=raw_token,
        )
        return (keycloak_user, raw_token)
