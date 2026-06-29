"""
Authentication views — Login, Password Reset, User Profile.

Sonar fixes applied:
- Module-level logger (not inside method)
- logger.error/warning with % formatting (not f-strings)
- print() replaced with logger.warning()
- Unused import DjangoLoginSerializer removed
- PasswordResetSerializer imported at module level
"""
import logging

from django.contrib.auth.models import User
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rbac.models import UserProfile
from .authentication import KeycloakAuthentication
from .serializers import LoginSerializer, PasswordResetSerializer
from .services import KeycloakService

logger = logging.getLogger(__name__)


# ── Login ─────────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    """
    Login endpoint — authenticates via Keycloak with Django fallback.
    POST /api/auth/login/
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('Login validation failed: %s', serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        login_field = serializer.validated_data['login_field']
        password    = serializer.validated_data['password']
        bypass_kc   = serializer.validated_data.get('bypass_keycloak', False)

        logger.info('Login attempt for: %s', login_field)

        try:
            keycloak_service = KeycloakService()
            token_response = self._authenticate(keycloak_service, login_field, password, bypass_kc)
            access_token   = token_response.get('access_token')
        except Exception as exc:
            return self._auth_error_response(exc)

        # Load Django profile
        try:
            profile = keycloak_service.get_user_profile(access_token)
        except Exception as profile_error:
            logger.error('Failed to get user profile: %s', profile_error)
            return Response({
                'error': 'User authenticated but profile incomplete',
                'detail': str(profile_error),
                'access_token': access_token,
            }, status=status.HTTP_403_FORBIDDEN)

        # First-login enforcement
        if profile.get('is_first_login'):
            return self._handle_first_login(keycloak_service, profile)

        logger.info('Login successful for %s', login_field)
        return Response({
            'access_token': access_token,
            'token_type': token_response.get('token_type', 'Bearer'),
            'expires_in': token_response.get('expires_in'),
            'user': profile,
            'auth_source': token_response.get('source', 'keycloak'),
        }, status=status.HTTP_200_OK)

    # ── private helpers ───────────────────────────────────────────────────────

    def _authenticate(self, keycloak_service, login_field, password, bypass_kc):
        """Try Keycloak then Django fallback. Raises on total failure."""
        if bypass_kc:
            logger.info('Attempting Django-only authentication for %s', login_field)
            try:
                token_response = keycloak_service.authenticate_user_django_only(login_field, password)
                logger.info('Django authentication successful for %s', login_field)
                return token_response
            except Exception as django_error:
                logger.error('Django authentication failed: %s', django_error)
                raise

        # Keycloak first
        logger.info('Attempting Keycloak authentication for %s', login_field)
        try:
            token_response = keycloak_service.authenticate_user(login_field, password)
            logger.info('Keycloak authentication successful for %s', login_field)
            return token_response
        except Exception as keycloak_error:
            error_msg = str(keycloak_error)
            logger.warning('Keycloak auth failed: %s — trying Django fallback', error_msg)
            try:
                token_response = keycloak_service.authenticate_user_django_only(login_field, password)
                logger.info('Django fallback authentication successful for %s', login_field)
                return token_response
            except Exception as django_error:
                logger.error('Both Keycloak and Django auth failed: %s', django_error)
                raise

    def _handle_first_login(self, keycloak_service, profile):
        """Send first-login email and return 403 instructing password reset."""
        try:
            reset_token = keycloak_service.generate_first_login_token(profile['username'])
            user = User.objects.get(username=profile['username'])
            keycloak_service.send_first_login_email(user, reset_token)
        except Exception as reset_error:
            logger.error('Failed to send first login email: %s', reset_error)
            return Response({
                'error': 'Première connexion détectée',
                'detail': f"Impossible d'envoyer l'email de réinitialisation : {reset_error}",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'error': 'Première connexion détectée. Veuillez vérifier votre email pour modifier votre mot de passe.',
            'detail': 'Un email de réinitialisation a été envoyé.',
            'email': profile.get('email'),
        }, status=status.HTTP_403_FORBIDDEN)

    @staticmethod
    def _auth_error_response(exc):
        detail = str(exc)
        logger.error('Unhandled login error: %s', detail)
        sc = (
            status.HTTP_403_FORBIDDEN
            if 'not fully set up' in detail.lower() or 'required action' in detail.lower()
            else status.HTTP_401_UNAUTHORIZED
        )
        return Response({'error': 'Authentication failed', 'detail': detail}, status=sc)


# ── Password Reset ────────────────────────────────────────────────────────────

class PasswordResetView(APIView):
    """
    Reset password after first login using a secure one-time token.
    POST /api/auth/reset-password/
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'detail': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            keycloak_service = KeycloakService()
            decoded  = keycloak_service.verify_first_login_token(serializer.validated_data['token'])
            username = decoded.get('username')

            user    = User.objects.get(username=username)
            profile = UserProfile.objects.get(user=user)

            user.set_password(serializer.validated_data['new_password'])
            user.save()

            profile.is_first_login = False
            profile.save()

            self._sync_keycloak_password(keycloak_service, profile, serializer.validated_data['new_password'])

            return Response({
                'status': 'success',
                'message': 'Mot de passe mis à jour avec succès. Vous pouvez maintenant vous connecter.',
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({'error': 'Utilisateur introuvable'}, status=status.HTTP_404_NOT_FOUND)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Profil utilisateur introuvable'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response(
                {'error': 'Impossible de réinitialiser le mot de passe', 'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @staticmethod
    def _sync_keycloak_password(keycloak_service, profile, new_password):
        """Attempt to sync the new password to Keycloak (non-fatal)."""
        if profile.keycloak_id:
            try:
                keycloak_service.update_user_password_in_keycloak(profile.keycloak_id, new_password)
            except Exception as kc_error:
                logger.warning('Keycloak password update warning: %s', kc_error)


# ── User Profile ──────────────────────────────────────────────────────────────

class GetUserProfileView(APIView):
    """
    Get current user's profile (role, department, theme).
    GET /api/auth/me/
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [KeycloakAuthentication]

    def get(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return Response(
                {'error': 'Missing or invalid Authorization header'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        access_token = auth_header[7:]
        try:
            profile = KeycloakService().get_user_profile(access_token)
            return Response(profile, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response(
                {'error': 'Failed to load user profile', 'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
