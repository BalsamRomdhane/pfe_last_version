import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from django.contrib.auth.models import User
from rbac.models import UserProfile

print('PROFILE_COUNT=', UserProfile.objects.count())
for user in User.objects.order_by('username'):
    profile = UserProfile.objects.filter(user=user).first()
    role = profile.role.code if profile and profile.role else None
    dept = profile.department.code if profile and profile.department else None
    print(
        f"USER={user.username} EMAIL={user.email} STAFF={user.is_staff} ACTIVE={user.is_active} "
        f"ROLE={role} DEPT={dept} HASH_PREFIX={user.password.split('$')[0] if user.password else None}"
    )
