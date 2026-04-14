from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListCreateAPIView
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q

from authentication.authentication import KeycloakAuthentication
from authentication.permissions import IsAdmin, DepartmentAccess
from authentication.serializers import (
    UserCreateSerializer, 
    UserUpdateSerializer,
    UserDetailSerializer,
    UserProfileSerializer,
    DepartmentSerializer,
    RoleSerializer
)
from authentication.services import KeycloakService
from .models import UserProfile, Role, Department, AuditLog
from .signals import log_user_action


class UserListCreateView(APIView):
    """
    GET: List all users (ADMIN only) with pagination, search, and filtering
    POST: Create new user (ADMIN only) - creates in both Django and Keycloak
    """
    permission_classes = [IsAuthenticated, IsAdmin]
    authentication_classes = [KeycloakAuthentication]

    def get(self, request):
        """List all users with pagination, search, and filtering"""
        try:
            # Get query parameters
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 10))
            search = request.query_params.get('search', '')
            role = request.query_params.get('role', '')
            department = request.query_params.get('department', '')
            
            # Base queryset
            profiles = UserProfile.objects.select_related('user', 'role', 'department').all()
            
            # Apply search filter
            if search:
                profiles = profiles.filter(
                    Q(user__username__icontains=search) |
                    Q(user__email__icontains=search) |
                    Q(user__first_name__icontains=search) |
                    Q(user__last_name__icontains=search)
                )
            
            # Apply role filter
            if role:
                profiles = profiles.filter(role__code=role)
            
            # Apply department filter
            if department:
                profiles = profiles.filter(department__code=department)
            
            # Apply ordering
            order_by = request.query_params.get('order_by', '-created_at')
            profiles = profiles.order_by(order_by)
            
            # Calculate pagination
            total_count = profiles.count()
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            
            paginated_profiles = profiles[start_idx:end_idx]
            
            users_data = []
            for profile in paginated_profiles:
                user = profile.user
                users_data.append({
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': profile.role.code,
                    'role_name': profile.role.name,
                    'department': profile.department.code if profile.department else None,
                    'department_name': profile.department.name if profile.department else None,
                    'date_naissance': profile.date_naissance.isoformat() if profile.date_naissance else None,
                    'is_first_login': profile.is_first_login,
                    'keycloak_id': profile.keycloak_id,
                    'created_at': profile.created_at.isoformat() if profile.created_at else None,
                })
            
            return Response({
                'status': 'success',
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total_count,
                    'total_pages': (total_count + page_size - 1) // page_size,
                },
                'count': len(users_data),
                'data': users_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': 'Failed to fetch users',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        """Create a new user in Django and Keycloak"""
        serializer = UserCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid input',
                'detail': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # Extract validated data
                username = serializer.validated_data['username']
                email = serializer.validated_data['email']
                password = serializer.validated_data['password']
                first_name = serializer.validated_data.get('first_name', '')
                last_name = serializer.validated_data.get('last_name', '')
                date_naissance = serializer.validated_data.get('date_naissance')
                role_code = serializer.validated_data['role']
                department_code = serializer.validated_data.get('department')

                # Get role and department
                try:
                    role = Role.objects.get(code=role_code)
                except Role.DoesNotExist:
                    if role_code in ['ADMIN', 'TEAMLEAD', 'EMPLOYEE']:
                        role_names = {
                            'ADMIN': 'Administrator',
                            'TEAMLEAD': 'Team Lead',
                            'EMPLOYEE': 'Employee',
                        }
                        role, _ = Role.objects.get_or_create(
                            code=role_code,
                            defaults={'name': role_names.get(role_code, role_code.title())}
                        )
                    else:
                        return Response({
                            'error': 'Role not found',
                            'detail': f'Role {role_code} does not exist'
                        }, status=status.HTTP_400_BAD_REQUEST)

                department = None
                if department_code:
                    try:
                        department = Department.objects.get(code=department_code)
                    except Department.DoesNotExist:
                        return Response({
                            'error': 'Department not found',
                            'detail': f'Department {department_code} does not exist'
                        }, status=status.HTTP_400_BAD_REQUEST)

                # Create user in Django
                django_user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )

                # Try to create user in Keycloak (failure is non-fatal)
                keycloak_service = KeycloakService()
                keycloak_id = None
                try:
                    keycloak_id = keycloak_service.create_user_in_keycloak(
                        username=username,
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name
                    )
                except Exception as kc_error:
                    # Log but don't fail - user can still work with Django
                    print(f'Keycloak user creation warning: {kc_error}')

                # Create UserProfile in Django
                user_profile = UserProfile.objects.create(
                    user=django_user,
                    role=role,
                    department=department,
                    keycloak_id=keycloak_id,
                    date_naissance=date_naissance,
                    is_first_login=True
                )

                response_data = {
                    'status': 'success',
                    'message': 'User created successfully',
                    'data': {
                        'id': django_user.id,
                        'username': django_user.username,
                        'email': django_user.email,
                        'first_name': django_user.first_name,
                        'last_name': django_user.last_name,
                        'role': user_profile.role.code,
                        'department': user_profile.department.code if user_profile.department else None,
                        'keycloak_id': keycloak_id,
                        'date_naissance': user_profile.date_naissance.isoformat() if user_profile.date_naissance else None,
                        'is_first_login': user_profile.is_first_login,
                    }
                }

                if not request.data.get('password'):
                    response_data['generated_password'] = password

                if keycloak_id is None:
                    response_data['keycloak_created'] = False
                    response_data['keycloak_error'] = 'Keycloak user creation failed or user already exists.'
                else:
                    response_data['keycloak_created'] = True

                return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                'error': 'Failed to create user',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class UserDetailView(APIView):
    """
    GET: Get user details
    PUT: Update user (ADMIN only)
    DELETE: Delete user (ADMIN only)
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [KeycloakAuthentication]

    def get(self, request, user_id):
        """Get user details"""
        try:
            user = User.objects.get(id=user_id)
            profile = UserProfile.objects.get(user=user)

            return Response({
                'status': 'success',
                'data': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': profile.role.code,
                    'role_name': profile.role.name,
                    'department': profile.department.code if profile.department else None,
                    'department_name': profile.department.name if profile.department else None,
                    'keycloak_id': profile.keycloak_id,
                    'created_at': profile.created_at.isoformat() if profile.created_at else None,
                }
            }, status=status.HTTP_200_OK)

        except (User.DoesNotExist, UserProfile.DoesNotExist):
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': 'Failed to fetch user',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, user_id):
        """Update user (ADMIN only)"""
        # Check if requester is ADMIN
        if not hasattr(request.user, 'roles') or 'ADMIN' not in request.user.roles:
            return Response({
                'error': 'Permission denied',
                'detail': 'Only admins can update users'
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = UserUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid input',
                'detail': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                user = User.objects.get(id=user_id)
                profile = UserProfile.objects.get(user=user)

                # Update user fields
                if 'first_name' in serializer.validated_data:
                    user.first_name = serializer.validated_data['first_name']
                if 'last_name' in serializer.validated_data:
                    user.last_name = serializer.validated_data['last_name']
                user.save()

                # Update profile fields
                if 'role' in serializer.validated_data:
                    role = Role.objects.get(code=serializer.validated_data['role'])
                    profile.role = role
                
                if 'department' in serializer.validated_data:
                    department_code = serializer.validated_data['department']
                    if department_code:
                        profile.department = Department.objects.get(code=department_code)
                    else:
                        profile.department = None
                
                profile.save()

                return Response({
                    'status': 'success',
                    'message': 'User updated successfully',
                    'data': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'role': profile.role.code,
                        'department': profile.department.code if profile.department else None,
                    }
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': 'Failed to update user',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, user_id):
        """Delete user (ADMIN only)"""
        # Check if requester is ADMIN
        if not hasattr(request.user, 'roles') or 'ADMIN' not in request.user.roles:
            return Response({
                'error': 'Permission denied',
                'detail': 'Only admins can delete users'
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            with transaction.atomic():
                user = User.objects.get(id=user_id)
                profile = UserProfile.objects.get(user=user)

                # Try to delete from Keycloak (non-fatal if fails)
                if profile.keycloak_id:
                    keycloak_service = KeycloakService()
                    try:
                        keycloak_service.delete_user_from_keycloak(profile.keycloak_id)
                    except Exception as e:
                        print(f'Keycloak deletion warning: {e}')

                # Delete Django user (cascade deletes UserProfile)
                username = user.username
                user.delete()

                return Response({
                    'status': 'success',
                    'message': f'User {username} deleted successfully'
                }, status=status.HTTP_200_OK)

        except (User.DoesNotExist, UserProfile.DoesNotExist):
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': 'Failed to delete user',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class DepartmentListView(APIView):
    """
    GET: List all departments
    POST: Create department (ADMIN only)
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [KeycloakAuthentication]

    def get(self, request):
        """List all departments"""
        try:
            departments = Department.objects.all()
            data = []
            for dept in departments:
                data.append({
                    'code': dept.code,
                    'name': dept.name,
                    'description': dept.description,
                    'theme_color': dept.theme_color,
                })
            
            return Response({
                'status': 'success',
                'count': len(data),
                'data': data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': 'Failed to fetch departments',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        """Create department (ADMIN only)"""
        # Check if requester is ADMIN
        if not hasattr(request.user, 'roles') or 'ADMIN' not in request.user.roles:
            return Response({
                'error': 'Permission denied',
                'detail': 'Only admins can create departments'
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = DepartmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid input',
                'detail': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            department = Department.objects.create(**serializer.validated_data)
            return Response({
                'status': 'success',
                'message': 'Department created successfully',
                'data': {
                    'code': department.code,
                    'name': department.name,
                    'description': department.description,
                    'theme_color': department.theme_color,
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                'error': 'Failed to create department',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class DepartmentDetailView(APIView):
    """
    PUT: Update department (ADMIN only)
    DELETE: Delete department (ADMIN only)
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [KeycloakAuthentication]

    def put(self, request, department_code):
        if not hasattr(request.user, 'roles') or 'ADMIN' not in request.user.roles:
            return Response({
                'error': 'Permission denied',
                'detail': 'Only admins can update departments'
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = DepartmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid input',
                'detail': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            department = Department.objects.get(code=department_code)
            for field, value in serializer.validated_data.items():
                setattr(department, field, value)
            department.save()
            return Response({
                'status': 'success',
                'message': 'Department updated successfully',
                'data': {
                    'code': department.code,
                    'name': department.name,
                    'description': department.description,
                    'theme_color': department.theme_color,
                }
            }, status=status.HTTP_200_OK)
        except Department.DoesNotExist:
            return Response({
                'error': 'Department not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': 'Failed to update department',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, department_code):
        if not hasattr(request.user, 'roles') or 'ADMIN' not in request.user.roles:
            return Response({
                'error': 'Permission denied',
                'detail': 'Only admins can delete departments'
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            department = Department.objects.get(code=department_code)
            department.delete()
            return Response({
                'status': 'success',
                'message': 'Department deleted successfully'
            }, status=status.HTTP_200_OK)
        except Department.DoesNotExist:
            return Response({
                'error': 'Department not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': 'Failed to delete department',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class RoleListView(APIView):
    """GET: List all roles"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [KeycloakAuthentication]

    def get(self, request):
        """List all roles"""
        try:
            roles = Role.objects.all()
            data = []
            for role in roles:
                data.append({
                    'code': role.code,
                    'name': role.name,
                    'description': role.description,
                })
            
            return Response({
                'status': 'success',
                'count': len(data),
                'data': data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': 'Failed to fetch roles',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

class AuditLogListView(APIView):
    """
    GET: List audit logs (ADMIN only) with filtering and pagination
    """
    permission_classes = [IsAuthenticated, IsAdmin]
    authentication_classes = [KeycloakAuthentication]

    def get(self, request):
        """List audit logs with filtering and pagination"""
        try:
            # Get query parameters
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))
            action = request.query_params.get('action', '')
            user_id = request.query_params.get('user_id', '')
            target_user_id = request.query_params.get('target_user_id', '')
            
            # Base queryset
            logs = AuditLog.objects.select_related('user', 'target_user').all()
            
            # Apply filters
            if action:
                logs = logs.filter(action=action)
            
            if user_id:
                logs = logs.filter(user_id=user_id)
            
            if target_user_id:
                logs = logs.filter(target_user_id=target_user_id)
            
            # Apply ordering (most recent first)
            logs = logs.order_by('-timestamp')
            
            # Calculate pagination
            total_count = logs.count()
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            
            paginated_logs = logs[start_idx:end_idx]
            
            logs_data = []
            for log in paginated_logs:
                logs_data.append({
                    'id': log.id,
                    'user': log.user.username if log.user else None,
                    'action': log.action,
                    'target_user': log.target_user.username if log.target_user else None,
                    'description': log.description,
                    'changes': log.changes,
                    'timestamp': log.timestamp.isoformat() if log.timestamp else None,
                    'ip_address': log.ip_address,
                })
            
            return Response({
                'status': 'success',
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total_count,
                    'total_pages': (total_count + page_size - 1) // page_size,
                },
                'count': len(logs_data),
                'data': logs_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': 'Failed to fetch audit logs',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)