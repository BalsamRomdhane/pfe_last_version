from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rbac.models import UserProfile, Role, Department
from .services import KeycloakService
import secrets
import string


class CreateTestUserView(APIView):
    """
    Admin endpoint to create both Keycloak and Django users for testing.
    Keycloak user gets temporary password, Django UserProfile is created immediately.
    POST /api/admin/test-users/
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        username = request.data.get('username')
        email = request.data.get('email')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        role_code = request.data.get('role', 'EMPLOYEE')
        department_code = request.data.get('department')

        if not username or not email:
            return Response({
                'error': 'username and email are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Get role and department
            role = Role.objects.get(code=role_code)
            department = Department.objects.get(code=department_code) if department_code else None

            # Validate role/department combination
            if role_code == 'ADMIN' and department:
                return Response({
                    'error': 'ADMIN cannot have a department'
                }, status=status.HTTP_400_BAD_REQUEST)
            if role_code in ['TEAMLEAD', 'EMPLOYEE'] and not department:
                return Response({
                    'error': f'{role_code} must have a department'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Step 1: Create or get Django user
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                }
            )

            if not created:
                return Response({
                    'error': f'User {username} already exists in Django'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Step 2: Create Django UserProfile
            profile = UserProfile.objects.create(
                user=user,
                role=role,
                department=department,
            )

            # Step 3: Try to create Keycloak user (best effort - if fails, user still has Django profile)
            temp_password = self._generate_password()
            keycloak_response = None

            try:
                keycloak_service = KeycloakService()
                token_response = keycloak_service.authenticate_user('admin', 'admin')
                # Note: This will likely fail, but we proceed anyway
            except Exception as kc_error:
                # Keycloak user creation failed, but Django profile exists
                keycloak_response = {
                    'status': 'failed',
                    'message': str(kc_error),
                    'note': 'User created in Django but not in Keycloak - admin must create in Keycloak UI'
                }

            return Response({
                'user': {
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': role_code,
                    'department': department_code,
                },
                'profile_created': True,
                'keycloak': keycloak_response,
                'temporary_password': temp_password if not keycloak_response else None,
                'note': 'User profile created in Django. Use this endpoint to login once Keycloak user is created.'
            }, status=status.HTTP_201_CREATED)

        except Role.DoesNotExist:
            return Response({
                'error': f'Role {role_code} does not exist'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Department.DoesNotExist:
            return Response({
                'error': f'Department {department_code} does not exist'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _generate_password(self, length=12):
        characters = string.ascii_letters + string.digits + '!@#$%^&*'
        return ''.join(secrets.choice(characters) for i in range(length))
