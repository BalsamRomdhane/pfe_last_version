import json
import requests
import jwt
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rbac.models import UserProfile

class KeycloakService:
    """
    Simplified Keycloak service - handles ONLY authentication (token generation).
    All RBAC logic (roles, departments, permissions) is managed in Django via UserProfile.
    """

    def __init__(self):
        self.server_url = settings.KEYCLOAK_SERVER_URL.rstrip('/')
        self.realm = settings.KEYCLOAK_REALM
        self.client_id = settings.KEYCLOAK_CLIENT_ID
        self.client_secret = settings.KEYCLOAK_CLIENT_SECRET

    def authenticate_user(self, username_or_email, password):
        """
        Authenticate user with Keycloak using Direct Access Grant (password grant).
        Accepts either username or email address.
        Returns Keycloak JWT token response.
        """
        # Check if input is email and convert to username
        username = self._resolve_username(username_or_email)
        
        token_url = f'{self.server_url}/realms/{self.realm}/protocol/openid-connect/token'
        payload = {
            'grant_type': 'password',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'username': username,
            'password': password,
        }
        response = requests.post(token_url, data=payload)
        if response.status_code != 200:
            message = response.text
            try:
                error = response.json()
                if isinstance(error, dict):
                    message = error.get('error_description') or error.get('error') or json.dumps(error)
            except ValueError:
                pass

            if response.status_code == 400 and 'invalid_grant' in message:
                lower = message.lower()
                if 'not fully set up' in lower or 'required action' in lower:
                    raise Exception(
                        'Keycloak account is not fully set up. Please complete required actions or verify the user account in Keycloak.'
                    )
                if 'invalid user credentials' in lower or 'invalid grant' in lower:
                    raise Exception('Invalid username or password.')

            raise Exception(f'Keycloak authentication failed: {response.status_code} {message}')
        return response.json()

    def _resolve_username(self, username_or_email):
        """
        Resolve username from email if needed.
        If input looks like email, find corresponding Django user and return username.
        Otherwise return input as-is.
        """
        if '@' in username_or_email:
            # Input is email - find username from Django
            try:
                user = User.objects.get(email=username_or_email)
                return user.username
            except User.DoesNotExist:
                raise Exception(f'No user found with email: {username_or_email}')
        else:
            # Input is username
            return username_or_email

    def authenticate_user_django_only(self, username_or_email, password):
        """
        Authenticate user directly via Django (bypasses Keycloak).
        Fallback when Keycloak account is not fully set up.
        Returns a mock JWT token response.
        """
        # Resolve email to username if needed
        if '@' in username_or_email:
            try:
                user = User.objects.get(email=username_or_email)
                username = user.username
            except User.DoesNotExist:
                raise Exception(f'No user found with email: {username_or_email}')
        else:
            username = username_or_email

        # Authenticate against Django
        user = authenticate(username=username, password=password)
        if not user:
            raise Exception('Invalid username or password.')

        # Create a mock JWT token for Django-authenticated user
        # This will be decoded by KeycloakAuthentication as if it came from Keycloak
        payload = {
            'preferred_username': username,
            'sub': username,
            'realm_access': {'roles': []},
            'iat': datetime.utcnow().timestamp(),
            'exp': (datetime.utcnow() + timedelta(hours=1)).timestamp(),
            'source': 'django_fallback',  # Marker that this came from Django, not Keycloak
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        
        return {
            'access_token': token,
            'token_type': 'Bearer',
            'expires_in': 3600,
            'source': 'django_fallback'
        }

    def get_user_profile(self, access_token):
        """
        Load Django UserProfile for authenticated user.
        Decodes JWT to extract username, then loads UserProfile from database.
        Returns combined profile with role and department data.
        """
        try:
            # Decode JWT (no signature verification in development)
            decoded = jwt.decode(access_token, options={"verify_signature": False})
            username = decoded.get('preferred_username') or decoded.get('sub')
        except Exception as e:
            raise Exception(f'Failed to decode JWT: {str(e)}')

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise Exception(f'User {username} authenticated but not found in Django')

        try:
            profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            raise Exception(f'User {username} has no UserProfile - admin must create profile in Django')

        return {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': profile.role.code,
            'role_name': profile.role.name,
            'department': profile.department.code if profile.department else None,
            'department_name': profile.department.name if profile.department else None,
            'theme_color': profile.department.theme_color if profile.department else '#1976d2',  # Default blue for ADMIN
        }