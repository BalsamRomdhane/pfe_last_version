import os, json, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
import django
django.setup()
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from pathlib import Path
from rbac.models import UserProfile

print('DATABASE_ENGINE =', settings.DATABASES['default'].get('ENGINE'))
print('DATABASE_NAME =', settings.DATABASES['default'].get('NAME'))
print('DATABASE_URL =', os.getenv('DATABASE_URL'))
print('USE_TOPLEVEL_DB =', os.getenv('USE_TOPLEVEL_DB'))
print('SWAPPED_TO_TOPLEVEL_DB =', os.getenv('SWAPPED_TO_TOPLEVEL_DB'))

for username in ['admin1', 'admin', 'demo']:
    user = User.objects.filter(username=username).first()
    print(f'USER {username}: exists={user is not None}')
    if user:
        print(f'  email={user.email} active={user.is_active}')
        print(f'  password_hasher={user.password.split("$")[0] if user.password else None}')
        print(f'  auth_check_default={authenticate(username=username, password="Admin1234!") is not None}')
        print(f'  auth_check_alt={authenticate(username=username, password="admin1234") is not None}')
        profile = UserProfile.objects.filter(user=user).first()
        print(f'  profile_exists={profile is not None}')
        if profile:
            print(f'  role={profile.role.code if profile.role else None}')

print('ALL_USERS=', list(User.objects.values_list('username', 'email')[:20]))
print('DB_EXISTS=', Path(str(settings.DATABASES['default'].get('NAME'))).exists())
