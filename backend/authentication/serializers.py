from rest_framework import serializers
from django.contrib.auth.models import User
from rbac.models import UserProfile, Role, Department, AuditLog

class LoginSerializer(serializers.Serializer):
    """
    Login serializer that accepts either username or email.
    At least one of username or email must be provided.
    """
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField()
    bypass_keycloak = serializers.BooleanField(required=False, default=False)

    def validate(self, data):
        """Ensure either username or email is provided"""
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        
        if not username and not email:
            raise serializers.ValidationError("Either username or email must be provided")
        
        # Keep the non-empty one as 'username' for the rest of the flow
        data['login_field'] = email if email else username
        
        return data

class DjangoLoginSerializer(serializers.Serializer):
    """
    Django-only login serializer that bypasses Keycloak.
    Authenticates directly against Django User model.
    """
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField()

class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for Department model"""
    class Meta:
        model = Department
        fields = ['code', 'name', 'description', 'theme_color']

class RoleSerializer(serializers.ModelSerializer):
    """Serializer for Role model"""
    class Meta:
        model = Role
        fields = ['code', 'name', 'description']

class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile with nested role and department"""
    role = RoleSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = ['username', 'email', 'role', 'department', 'created_at', 'updated_at', 'keycloak_id']

class UserDetailSerializer(serializers.Serializer):
    """Detailed user info returned from API"""
    username = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    role = serializers.CharField()
    role_name = serializers.CharField()
    department = serializers.CharField(allow_null=True)
    department_name = serializers.CharField(allow_null=True)
    theme_color = serializers.CharField()

class UserCreateSerializer(serializers.Serializer):
    """Serializer for creating a new user"""
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8)
    first_name = serializers.CharField(required=False, default='')
    last_name = serializers.CharField(required=False, default='')
    role = serializers.ChoiceField(choices=['ADMIN', 'TEAMLEAD', 'EMPLOYEE'])
    department = serializers.ChoiceField(
        choices=['DIGITAL', 'AERONAUTIQUE', 'AUTOMOBILE', 'QUALITE'], 
        required=False,
        allow_null=True
    )

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        return value
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def validate(self, data):
        role = data.get('role')
        department = data.get('department')
        
        if role == 'ADMIN' and department:
            raise serializers.ValidationError("ADMIN role cannot have a department")
        
        if role in ['TEAMLEAD', 'EMPLOYEE'] and not department:
            raise serializers.ValidationError(f"{role} role must have a department")
        
        return data

class UserUpdateSerializer(serializers.Serializer):
    """Serializer for updating user"""
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    role = serializers.ChoiceField(
        choices=['ADMIN', 'TEAMLEAD', 'EMPLOYEE'],
        required=False
    )
    department = serializers.ChoiceField(
        choices=['DIGITAL', 'AERONAUTIQUE', 'AUTOMOBILE', 'QUALITE'],
        required=False,
        allow_null=True
    )

    def validate(self, data):
        role = data.get('role')
        department = data.get('department')
        
        if role is not None:
            if role == 'ADMIN' and department:
                raise serializers.ValidationError("ADMIN role cannot have a department")
            
            if role in ['TEAMLEAD', 'EMPLOYEE'] and not department and 'department' in data:
                raise serializers.ValidationError(f"{role} role must have a department")
        
        return data


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for AuditLog model"""
    user_username = serializers.CharField(source='user.username', read_only=True, allow_null=True)
    target_user_username = serializers.CharField(source='target_user.username', read_only=True, allow_null=True)
    
    class Meta:
        model = AuditLog
        fields = ['id', 'user_username', 'action', 'target_user_username', 'description', 'changes', 'timestamp', 'ip_address']


    def validate(self, data):
        role = data.get('role')
        department = data.get('department')
        
        if role is not None:
            if role == 'ADMIN' and department:
                raise serializers.ValidationError("ADMIN role cannot have a department")
            
            if role in ['TEAMLEAD', 'EMPLOYEE'] and not department and 'department' in data:
                raise serializers.ValidationError(f"{role} role must have a department")
        
        return data
