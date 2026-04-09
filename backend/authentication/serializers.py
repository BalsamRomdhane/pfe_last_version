from rest_framework import serializers

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

class UserCreateSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=['ADMIN', 'TEAMLEAD', 'EMPLOYEE'])
    department = serializers.ChoiceField(choices=['DIGITAL', 'AERONAUTIQUE', 'AUTOMOBILE', 'QUALITE'], required=False)

    def validate(self, data):
        role = data.get('role')
        department = data.get('department')
        if role == 'ADMIN' and department:
            raise serializers.ValidationError("ADMIN cannot have a department")
        if role in ['TEAMLEAD', 'EMPLOYEE'] and not department:
            raise serializers.ValidationError("TEAMLEAD and EMPLOYEE must have a department")
        return data
