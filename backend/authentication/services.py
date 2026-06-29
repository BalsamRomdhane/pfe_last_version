"""
services.py — KeycloakService: token issuance, user management, profile loading.

JWT validation is delegated entirely to jwt_utils — no jwt.decode() call here.
SonarQube S5659: decode_token() / decode_first_login_token() always verify
the signature; see jwt_utils.py for the full compliance documentation.
"""
import json
import logging
import time

import jwt
import requests
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.mail import send_mail
from rbac.models import UserProfile

from .jwt_utils import decode_first_login_token, decode_token

logger = logging.getLogger(__name__)


class KeycloakService:
    """
    Handles Keycloak authentication and user management.

    Responsibilities:
      - Obtain tokens from Keycloak (password grant / client credentials)
      - Issue Django-signed HS256 tokens when Keycloak is unavailable
      - Generate and verify first-login reset tokens
      - Load UserProfile from the database after token validation
      - CRUD operations against the Keycloak Admin API
    """

    def __init__(self):
        self.server_url       = settings.KEYCLOAK_SERVER_URL.rstrip('/')
        self.realm            = settings.KEYCLOAK_REALM
        self.client_id        = settings.KEYCLOAK_CLIENT_ID
        self.client_secret    = settings.KEYCLOAK_CLIENT_SECRET
        self.admin_username   = getattr(settings, 'KEYCLOAK_ADMIN_USERNAME',   None)
        self.admin_password   = getattr(settings, 'KEYCLOAK_ADMIN_PASSWORD',   None)
        self.admin_client_id  = getattr(settings, 'KEYCLOAK_ADMIN_CLIENT_ID',  'admin-cli')
        self.admin_client_secret = getattr(settings, 'KEYCLOAK_ADMIN_CLIENT_SECRET', None)

    # ── Authentication ────────────────────────────────────────────────────────

    def authenticate_user(self, username_or_email: str, password: str) -> dict:
        """
        Obtain a Keycloak access token via the password grant.
        Returns the full Keycloak token response dict.
        """
        username = self._resolve_username(username_or_email)
        token_url = f'{self.server_url}/realms/{self.realm}/protocol/openid-connect/token'
        payload = {
            'grant_type':    'password',
            'client_id':     self.client_id,
            'client_secret': self.client_secret,
            'username':      username,
            'password':      password,
        }
        response = requests.post(token_url, data=payload)
        if response.status_code != 200:
            message = response.text
            try:
                error = response.json()
                if isinstance(error, dict):
                    message = (
                        error.get('error_description')
                        or error.get('error')
                        or json.dumps(error)
                    )
            except ValueError:
                pass

            if response.status_code == 400 and 'invalid_grant' in message:
                lower = message.lower()
                if 'not fully set up' in lower or 'required action' in lower:
                    raise Exception(
                        'Keycloak account is not fully set up. '
                        'Please complete required actions or verify the user account in Keycloak.'
                    )
                if 'invalid user credentials' in lower or 'invalid grant' in lower:
                    raise Exception('Invalid username or password.')

            raise Exception(
                f'Keycloak authentication failed: {response.status_code} {message}'
            )
        return response.json()

    def authenticate_user_django_only(self, username_or_email: str, password: str) -> dict:
        """
        Authenticate directly against Django (Keycloak bypass / fallback).
        Issues a short-lived HS256 token signed with settings.SECRET_KEY.
        The token is validated by decode_token() / decode_hs256_token() on
        every subsequent request — signature is always verified.
        """
        if '@' in username_or_email:
            try:
                user     = User.objects.get(email=username_or_email)
                username = user.username
            except User.DoesNotExist:
                raise Exception(f'No user found with email: {username_or_email}')
        else:
            username = username_or_email

        django_user = authenticate(username=username, password=password)
        if not django_user:
            raise Exception('Invalid username or password.')

        try:
            profile = UserProfile.objects.get(user=django_user)
        except UserProfile.DoesNotExist:
            raise Exception('User profile is required for RBAC authentication.')

        _now = int(time.time())
        token_payload = {
            'preferred_username': username,
            'sub':                username,
            'realm_access':       {'roles': [profile.role.code]},
            'attributes': {
                'department': [profile.department.code] if profile.department else [],
            },
            'iat':    _now,
            'exp':    _now + 3600,
            'source': 'django_fallback',
        }
        # jwt.encode() produces a signed HS256 token.
        # Validation on future requests uses decode_token() → decode_hs256_token()
        # which verifies the signature and all registered claims.
        token = jwt.encode(token_payload, settings.SECRET_KEY, algorithm='HS256')
        return {
            'access_token': token,
            'token_type':   'Bearer',
            'expires_in':   3600,
            'source':       'django_fallback',
        }

    # ── First-login reset token ───────────────────────────────────────────────

    def generate_first_login_token(self, username: str) -> str:
        """Issue a short-lived HS256 first-login / password-reset token."""
        _now = int(time.time())
        payload = {
            'username': username,
            'purpose':  'first_login',
            'iat':      _now,
            'exp':      _now + 5400,    # 90 minutes
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

    def verify_first_login_token(self, token: str) -> dict:
        """
        Validate a first-login reset token.

        Delegates to decode_first_login_token() which:
          - Calls decode_hs256_token() (signature + exp/nbf/iat verified)
          - Also checks the 'purpose' claim
        Raises ValueError / jwt.InvalidTokenError on any failure.
        """
        return decode_first_login_token(token)

    def send_first_login_email(self, user, token: str) -> None:
        """Send the password-reset email with the one-time link."""
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        reset_link   = f'{frontend_url}/reset-password?token={token}'
        subject      = 'Première connexion : réinitialisation de votre mot de passe'
        message = (
            f'Bonjour {user.first_name or user.last_name or user.username},\n\n'
            "Nous avons détecté que c'est votre première connexion.\n"
            'Veuillez cliquer sur le lien suivant pour définir un nouveau mot de passe :\n\n'
            f'{reset_link}\n\n'
            "Ce lien expire dans 90 minutes. "
            "Si vous n'avez pas demandé cette opération, ignorez ce message."
        )
        email_from = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com')
        send_mail(subject, message, email_from, [user.email], fail_silently=False)

    # ── Profile loading ───────────────────────────────────────────────────────

    def get_user_profile(self, access_token: str) -> dict:
        """
        Decode the access token (signature verified) and return the Django
        UserProfile data for the authenticated user.
        """
        try:
            decoded  = decode_token(access_token)
            username = decoded.get('preferred_username') or decoded.get('sub')
        except Exception as exc:
            raise Exception(f'Failed to decode JWT: {exc}') from exc

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise Exception(
                f'User "{username}" authenticated but not found in Django.'
            )

        try:
            profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            raise Exception(
                f'User "{username}" has no UserProfile — '
                'an admin must create the profile in Django.'
            )

        return {
            'username':        user.username,
            'email':           user.email,
            'first_name':      user.first_name,
            'last_name':       user.last_name,
            'role':            profile.role.code,
            'role_name':       profile.role.name,
            'department':      profile.department.code if profile.department else None,
            'department_name': profile.department.name if profile.department else None,
            'theme_color':     profile.department.theme_color if profile.department else '#1976d2',
            'is_first_login':  profile.is_first_login,
            'date_naissance':  profile.date_naissance.isoformat() if profile.date_naissance else None,
        }

    # ── Keycloak Admin API ────────────────────────────────────────────────────

    def _resolve_username(self, username_or_email: str) -> str:
        if '@' in username_or_email:
            try:
                return User.objects.get(email=username_or_email).username
            except User.DoesNotExist:
                raise Exception(f'No user found with email: {username_or_email}')
        return username_or_email

    def get_keycloak_admin_token(self) -> str:
        """Obtain an admin token from Keycloak (client credentials or password grant)."""
        errors = []

        if self.client_id and self.client_secret:
            token_url = f'{self.server_url}/realms/{self.realm}/protocol/openid-connect/token'
            payload   = {
                'grant_type':    'client_credentials',
                'client_id':     self.client_id,
                'client_secret': self.client_secret,
            }
            response = requests.post(token_url, data=payload)
            if response.status_code == 200:
                return response.json().get('access_token')
            errors.append(
                f'Service account token failed: {response.status_code} {response.text}'
            )

        if self.admin_username and self.admin_password and self.admin_client_id:
            token_url = f'{self.server_url}/realms/master/protocol/openid-connect/token'
            payload   = {
                'grant_type': 'password',
                'client_id':  self.admin_client_id,
                'username':   self.admin_username,
                'password':   self.admin_password,
            }
            if self.admin_client_secret:
                payload['client_secret'] = self.admin_client_secret
            response = requests.post(token_url, data=payload)
            if response.status_code == 200:
                return response.json().get('access_token')
            errors.append(
                f'Admin credentials token failed: {response.status_code} {response.text}'
            )

        raise Exception(
            'Failed to obtain Keycloak admin token. ' + ' | '.join(errors)
        )

    def create_user_in_keycloak(
        self, username, email, password, first_name='', last_name=''
    ) -> str | None:
        try:
            admin_token = self.get_keycloak_admin_token()
        except Exception as exc:
            logger.warning('Could not create user in Keycloak: %s', exc)
            return None

        url     = f'{self.server_url}/admin/realms/{self.realm}/users'
        headers = {'Authorization': f'Bearer {admin_token}', 'Content-Type': 'application/json'}
        payload = {
            'username':    username,
            'email':       email,
            'firstName':   first_name,
            'lastName':    last_name,
            'enabled':     True,
            'credentials': [{'type': 'password', 'value': password, 'temporary': False}],
        }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 201:
            location = response.headers.get('Location', '')
            return location.split('/')[-1] if location else None
        if response.status_code == 409:
            return None     # user already exists
        raise Exception(
            f'Failed to create user in Keycloak: {response.status_code} {response.text}'
        )

    def delete_user_from_keycloak(self, keycloak_id: str) -> bool:
        try:
            admin_token = self.get_keycloak_admin_token()
        except Exception as exc:
            logger.warning('Could not delete user from Keycloak: %s', exc)
            return False
        url     = f'{self.server_url}/admin/realms/{self.realm}/users/{keycloak_id}'
        headers = {'Authorization': f'Bearer {admin_token}'}
        response = requests.delete(url, headers=headers)
        return response.status_code in (200, 204)

    def update_user_password_in_keycloak(self, keycloak_id: str, password: str) -> bool:
        try:
            admin_token = self.get_keycloak_admin_token()
        except Exception as exc:
            logger.warning('Could not update password in Keycloak: %s', exc)
            return False
        url     = f'{self.server_url}/admin/realms/{self.realm}/users/{keycloak_id}/reset-password'
        headers = {'Authorization': f'Bearer {admin_token}', 'Content-Type': 'application/json'}
        payload = {'type': 'password', 'value': password, 'temporary': False}
        response = requests.put(url, json=payload, headers=headers)
        return response.status_code in (200, 204)

    def update_user_in_keycloak(
        self, keycloak_id, username=None, email=None, first_name=None, last_name=None
    ) -> bool:
        try:
            admin_token = self.get_keycloak_admin_token()
        except Exception as exc:
            logger.warning('Could not update user in Keycloak: %s', exc)
            return False
        payload = {}
        if username   is not None: payload['username']   = username
        if email      is not None: payload['email']      = email
        if first_name is not None: payload['firstName']  = first_name
        if last_name  is not None: payload['lastName']   = last_name
        if not payload:
            return True
        url     = f'{self.server_url}/admin/realms/{self.realm}/users/{keycloak_id}'
        headers = {'Authorization': f'Bearer {admin_token}', 'Content-Type': 'application/json'}
        response = requests.put(url, json=payload, headers=headers)
        return response.status_code in (200, 204)
