import os
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
import django

django.setup()

from django.contrib.auth.models import User
from rbac.models import UserProfile

rows = []
for user in User.objects.all():
    profile = UserProfile.objects.filter(user=user).first()
    if profile and profile.role and profile.role.code == 'ADMIN':
        rows.append({
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'role': profile.role.code,
            'department': profile.department.code if profile.department else None,
        })

print(json.dumps(rows, indent=2, ensure_ascii=False))
