from django.contrib.auth.models import User
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializers import LoginSerializer, DjangoLoginSerializer
from .services import KeycloakService
from .authentication import KeycloakAuthentication
from rbac.models import UserProfile


class LoginView(APIView):
    """
    Login endpoint: authenticates user with Keycloak, then returns user profile with role/department from Django.
    Supports fallback to Django-only authentication when Keycloak account is not fully set up.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            login_field = serializer.validated_data['login_field']  # Can be username or email
            password = serializer.validated_data['password']
            bypass_keycloak = serializer.validated_data.get('bypass_keycloak', False)
            
            try:
                keycloak_service = KeycloakService()
                
                # Try Keycloak first unless explicitly bypassed
                if not bypass_keycloak:
                    try:
                        # Step 1: Authenticate with Keycloak (get token)
                        token_response = keycloak_service.authenticate_user(login_field, password)
                        access_token = token_response.get('access_token')
                    except Exception as keycloak_error:
                        # If Keycloak is unavailable or account is not fully set up, fall back to Django auth.
                        error_msg = str(keycloak_error)
                        try:
                            token_response = keycloak_service.authenticate_user_django_only(login_field, password)
                            access_token = token_response.get('access_token')
                        except Exception as django_error:
                            return Response({
                                'error': 'Authentication failed',
                                'detail': str(django_error),
                                'keycloak_error': error_msg,
                                'note': 'Keycloak is unavailable or account not present. Tried Django fallback.'
                            }, status=status.HTTP_401_UNAUTHORIZED)
                else:
                    # Django-only authentication
                    try:
                        token_response = keycloak_service.authenticate_user_django_only(login_field, password)
                        access_token = token_response.get('access_token')
                    except Exception as django_error:
                        return Response({
                            'error': 'Authentication failed',
                            'detail': str(django_error)
                        }, status=status.HTTP_401_UNAUTHORIZED)
                
                # Step 2: Load user profile from Django database
                try:
                    profile = keycloak_service.get_user_profile(access_token)
                except Exception as profile_error:
                    # User authenticated but doesn't have Django profile
                    return Response({
                        'error': 'User authenticated but profile incomplete',
                        'detail': str(profile_error),
                        'access_token': access_token  # Still return token for admin to create profile
                    }, status=status.HTTP_403_FORBIDDEN)

                # Step 2.5: Enforce first-login reset if needed
                if profile.get('is_first_login'):
                    try:
                        reset_token = keycloak_service.generate_first_login_token(profile['username'])
                        user = User.objects.get(username=profile['username'])
                        keycloak_service.send_first_login_email(user, reset_token)
                    except Exception as reset_error:
                        return Response({
                            'error': 'Première connexion détectée',
                            'detail': f'Impossible d\'envoyer l\'email de réinitialisation : {reset_error}'
                        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                    return Response({
                        'error': 'Première connexion détectée. Veuillez vérifier votre email pour modifier votre mot de passe.',
                        'detail': 'Un email de réinitialisation a été envoyé.',
                        'email': profile.get('email')
                    }, status=status.HTTP_403_FORBIDDEN)
                
                # Step 3: Return token + profile
                return Response({
                    'access_token': access_token,
                    'token_type': token_response.get('token_type', 'Bearer'),
                    'expires_in': token_response.get('expires_in'),
                    'user': profile,
                    'auth_source': token_response.get('source', 'keycloak')
                }, status=status.HTTP_200_OK)
                
            except Exception as exc:
                detail = str(exc)
                status_code = status.HTTP_401_UNAUTHORIZED
                if 'not fully set up' in detail.lower() or 'required action' in detail.lower():
                    status_code = status.HTTP_403_FORBIDDEN
                return Response({
                    'error': 'Authentication failed',
                    'detail': detail
                }, status=status_code)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetView(APIView):
    """
    Reset the user's password after first login using a secure one-time token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        from .serializers import PasswordResetSerializer
        serializer = PasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid input',
                'detail': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            keycloak_service = KeycloakService()
            decoded = keycloak_service.verify_first_login_token(serializer.validated_data['token'])
            username = decoded.get('username')
            user = User.objects.get(username=username)
            profile = UserProfile.objects.get(user=user)

            user.set_password(serializer.validated_data['new_password'])
            user.save()

            profile.is_first_login = False
            profile.save()

            if profile.keycloak_id:
                try:
                    keycloak_service.update_user_password_in_keycloak(profile.keycloak_id, serializer.validated_data['new_password'])
                except Exception as kc_error:
                    print(f'Keycloak password update warning: {kc_error}')

            return Response({
                'status': 'success',
                'message': 'Mot de passe mis à jour avec succès. Vous pouvez maintenant vous connecter.'
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'error': 'Utilisateur introuvable'
            }, status=status.HTTP_404_NOT_FOUND)
        except UserProfile.DoesNotExist:
            return Response({
                'error': 'Profil utilisateur introuvable'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': 'Impossible de réinitialiser le mot de passe',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class GetUserProfileView(APIView):
    """
    Get current user's profile: returns role, department, and theme color from Django UserProfile.
    Requires valid Keycloak JWT in Authorization header.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [KeycloakAuthentication]

    def get(self, request):
        try:
            # request.user is set by KeycloakAuthentication
            keycloak_service = KeycloakService()
            
            # Extract token from request (KeycloakAuthentication adds it)
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if not auth_header.startswith('Bearer '):
                return Response({
                    'error': 'Missing or invalid Authorization header'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            access_token = auth_header[7:]  # Remove 'Bearer ' prefix
            profile = keycloak_service.get_user_profile(access_token)
            
            return Response(profile, status=status.HTTP_200_OK)
            
        except Exception as exc:
            return Response({
                'error': 'Failed to load user profile',
                'detail': str(exc)
            }, status=status.HTTP_400_BAD_REQUEST)

