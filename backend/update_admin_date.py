import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from django.contrib.auth.models import User
from rbac.models import UserProfile

user = User.objects.filter(email='admin@enterprise.local').first()
if not user:
    print('USER_NOT_FOUND')
    raise SystemExit(1)

profile, created = UserProfile.objects.get_or_create(
    user=user,
    defaults={'role_id': 1, 'date_naissance': '1990-01-01', 'is_first_login': False}
)
if created:
    print('PROFILE_CREATED')
else:
    profile.date_naissance = '1990-01-01'
    profile.is_first_login = False
    profile.save()
    print('PROFILE_UPDATED')
