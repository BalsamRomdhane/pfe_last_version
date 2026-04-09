import os
import sys
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')

from django import setup
setup()
from authentication.services import KeycloakService


def create_demo_user(username='demo-employee', email='demo-employee@example.com', role='EMPLOYEE', department='DIGITAL'):
    try:
        service = KeycloakService()
        print('Admin token source:', getattr(service, 'admin_token_source', 'unknown'))
        password = 'Demo1234!'
        user_data = {
            'username': username,
            'email': email,
            'enabled': True,
            'requiredActions': ['UPDATE_PASSWORD'],
            'attributes': {'department': [department]},
        }

        existing = service.get_user_id(username)
        if existing:
            print(f'User {username} already exists with id {existing}. Updating password and role.')
            service.set_user_password(existing, password, temporary=True)
            service.assign_role(existing, role)
            user_id = existing
        else:
            user_id = service.create_user(user_data)
            service.set_user_password(user_id, password, temporary=True)
            service.assign_role(user_id, role)

        print(json.dumps({
            'user_id': user_id,
            'username': username,
            'email': email,
            'role': role,
            'department': department,
            'temporary_password': password,
        }, indent=2))
    except Exception as exc:
        print('Test user creation failed:', str(exc))
        raise


if __name__ == '__main__':
    create_demo_user()