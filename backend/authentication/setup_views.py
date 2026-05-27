from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from rbac.models import UserProfile, Role, Department
import jwt
from datetime import datetime, timedelta


class InitializeAdminView(APIView):
    """
    One-time admin initialization endpoint (disable after first use).
    Creates both Keycloak and Django admin accounts.
    
    POST /api/auth/setup-admin/
    {
        "username": "admin",
        "password": "YourSecurePassword",
        "email": "admin@example.com"
    }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """Initialize the very first admin account"""
        
        # Check if any admin already exists (security measure)
        admin_count = User.objects.filter(is_staff=True).count()
        if admin_count > 0:
            # Admin already exists, don't create another
            admins = User.objects.filter(profile__role__code='ADMIN')
            if admins.exists():
                return Response({
                    'error': 'Admin account already exists',
                    'admin': admins.first().username
                }, status=status.HTTP_403_FORBIDDEN)
        
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '').strip()
        email = request.data.get('email', '').strip()
        first_name = request.data.get('first_name', 'Admin').strip()
        last_name = request.data.get('last_name', 'User').strip()

        # Validation
        if not username or len(username) < 3:
            return Response({
                'error': 'Username must be at least 3 characters'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not password or len(password) < 8:
            return Response({
                'error': 'Password must be at least 8 characters'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not email or '@' not in email:
            return Response({
                'error': 'Valid email required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Step 1: Create Django user
            if User.objects.filter(username=username).exists():
                return Response({
                    'error': f'Username {username} already exists'
                }, status=status.HTTP_400_BAD_REQUEST)

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=True,  # Mark as Django staff/admin
            )

            # Step 2: Create UserProfile with ADMIN role
            admin_role = Role.objects.get(code='ADMIN')
            profile = UserProfile.objects.create(
                user=user,
                role=admin_role,
                department=None,
            )

            # Step 3: Generate a test JWT (for immediate testing)
            payload = {
                'preferred_username': username,
                'sub': str(user.id),
                'email': email,
                'exp': datetime.utcnow() + timedelta(hours=24),
                'iat': datetime.utcnow(),
            }
            test_token = jwt.encode(payload, 'secret-key', algorithm='HS256')

            return Response({
                'status': 'success',
                'message': 'Admin account created successfully',
                'admin': {
                    'username': username,
                    'email': email,
                    'role': 'ADMIN',
                    'role_name': 'Administrator',
                    'department': None,
                    'theme_color': '#1976d2',
                },
                'credentials': {
                    'username': username,
                    'password': '[as provided]',
                },
                'instructions': {
                    '1': 'Admin account created in Django',
                    '2': 'Create matching user in Keycloak:',
                    '2a': '  Option A: Via Keycloak UI (http://localhost:8081)',
                    '2b': '  Option B: Using Django management command',
                    '3': 'After Keycloak user created, login at:',
                    '3_url': 'POST http://localhost:8000/api/auth/login/',
                },
                'test_token': test_token[:50] + '...',
                'note': 'Use test_token to access /api/auth/me/ for immediate testing'
            }, status=status.HTTP_201_CREATED)

        except Role.DoesNotExist:
            return Response({
                'error': 'ADMIN role not found - run init_rbac management command first'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetAdminStatusView(APIView):
    """
    Check current admin account status.
    GET /api/auth/admin-status/
    """
    permission_classes = [AllowAny]

    def get(self, request):
        """Get information about admin accounts"""
        admins = User.objects.filter(profile__role__code='ADMIN')
        
        if not admins.exists():
            return Response({
                'status': 'no_admin',
                'message': 'No admin account exists',
                'action': 'POST to /api/auth/setup-admin/ to create admin',
            }, status=status.HTTP_200_OK)
        
        admin_list = []
        for admin in admins:
            profile = admin.profile
            admin_list.append({
                'username': admin.username,
                'email': admin.email,
                'role': profile.role.code,
                'created': admin.date_joined.isoformat(),
            })
        
        return Response({
            'status': 'admin_exists',
            'admin_count': admins.count(),
            'admins': admin_list,
            'next_step': 'Setup Keycloak user with same username for full authentication'
        }, status=status.HTTP_200_OK)
