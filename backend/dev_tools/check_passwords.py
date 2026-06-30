import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
import django

django.setup()

from django.contrib.auth import authenticate
from django.contrib.auth.models import User

candidates = [
    'admin',
    'Admin1234!',
    'admin1234',
    'Admin1234',
    'password',
    'Password123!',
    '123456',
    'admin1',
    'admin@enterprise.local'
]

for username in ['admin', 'admin1']:
    user = User.objects.filter(username=username).first()
    print(f'USER={username}')
    if not user:
        print('  not found')
        continue
    print(f'  email={user.email}')
    print(f'  hash_prefix={user.password.split("$")[0] if user.password else None}')
    for pwd in candidates:
        if authenticate(username=username, password=pwd):
            print(f'  PASSWORD_MATCH={pwd!r}')
    print('  check_password(admin)=', user.check_password('admin'))
    print('  check_password(Admin1234!)=', user.check_password('Admin1234!'))
    print('  check_password(admin1234)=', user.check_password('admin1234'))
