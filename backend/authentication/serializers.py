from datetime import datetime
from rest_framework import serializers
from django.contrib.auth.models import User
from rbac.models import UserProfile, Role, Department, AuditLog

class LoginSerializer(serializers.Serializer):
    """
    Login serializer that accepts either username, email, or login.
    At least one of username, email or login must be provided.
    """
    login = serializers.CharField(required=False, allow_blank=True)
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField()
    bypass_keycloak = serializers.BooleanField(required=False, default=False)

    def validate(self, data):
        """Ensure either username, email, or login is provided"""
        login = data.get('login', '').strip()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()

        if not login and not username and not email:
            raise serializers.ValidationError("Either username, email, or login must be provided")

        # Prefer explicit login, then email, then username.
        data['login_field'] = login or email or username
        return data

class DjangoLoginSerializer(serializers.Serializer):
    """
    Django-only login serializer that bypasses Keycloak.
    Authenticates directly against Django User model.
    """
    login = serializers.CharField(required=False, allow_blank=True)
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
    username = serializers.CharField(max_length=150, required=False, allow_blank=True)
    nom = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField()
    date_naissance = serializers.CharField(required=True)
    password = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True, default='')
    last_name = serializers.CharField(required=False, allow_blank=True, default='')
    role = serializers.ChoiceField(choices=['ADMIN', 'TEAMLEAD', 'EMPLOYEE'])
    department = serializers.ChoiceField(
        choices=['DIGITAL', 'AERONAUTIQUE', 'AUTOMOBILE', 'QUALITE'], 
        required=False,
        allow_null=True
    )

    def validate_username(self, value):
        if value and User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        return value
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def validate_password(self, value):
        if value and len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long")
        return value

    def validate_date_naissance(self, value):
        value = value.strip()
        for fmt in ['%d/%m/%Y', '%Y-%m-%d']:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        raise serializers.ValidationError("date_naissance must be in DD/MM/YYYY or YYYY-MM-DD format")

    def validate(self, data):
        role = data.get('role')
        department = data.get('department')
        
        if role == 'ADMIN' and department:
            raise serializers.ValidationError("ADMIN role cannot have a department")
        
        if role in ['TEAMLEAD', 'EMPLOYEE'] and not department:
            raise serializers.ValidationError(f"{role} role must have a department")

        username = data.get('username', '').strip()
        email = data.get('email')
        if not username:
            base_username = email.split('@')[0]
            username = base_username
            idx = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{idx}"
                idx += 1
            data['username'] = username

        if not data.get('nom'):
            explicit_first_name = (self.initial_data.get('first_name') or '').strip()
            explicit_last_name = (self.initial_data.get('last_name') or '').strip()
            data['nom'] = explicit_first_name or explicit_last_name or ''

        if not data.get('password'):
            explicit_first_name = (self.initial_data.get('first_name') or '').strip()
            password_base = (
                explicit_first_name or
                data.get('username', '').strip() or
                data.get('nom', '').strip()
            )
            date_naissance = data['date_naissance']
            password = f"{password_base}{date_naissance.strftime('%d%m%Y')}".lower().replace(' ', '')
            data['password'] = password

        if len(data['password']) < 8:
            raise serializers.ValidationError("Generated password must be at least 8 characters long")

        # Always set first_name/last_name from nom if the user doesn't pass them explicitly
        if not data.get('first_name'):
            data['first_name'] = data['nom']
        if not data.get('last_name'):
            data['last_name'] = data['nom']

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

class PasswordResetSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)
    confirm_password = serializers.CharField(min_length=8)

    def validate(self, data):
        if data.get('new_password') != data.get('confirm_password'):
            raise serializers.ValidationError("Les mots de passe ne correspondent pas.")
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
