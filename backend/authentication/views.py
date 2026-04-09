from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializers import LoginSerializer, DjangoLoginSerializer
from .services import KeycloakService
from .authentication import KeycloakAuthentication


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
                        # If Keycloak fails with "not fully set up", try Django fallback
                        error_msg = str(keycloak_error).lower()
                        if 'not fully set up' in error_msg or 'required action' in error_msg:
                            try:
                                token_response = keycloak_service.authenticate_user_django_only(login_field, password)
                                access_token = token_response.get('access_token')
                            except Exception as django_error:
                                return Response({
                                    'error': 'Authentication failed',
                                    'detail': str(django_error),
                                    'note': 'Keycloak account needs setup. You can try with bypass_keycloak=true in the request body.'
                                }, status=status.HTTP_401_UNAUTHORIZED)
                        else:
                            raise keycloak_error
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

