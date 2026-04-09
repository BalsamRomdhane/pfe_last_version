#!/usr/bin/env python3
"""
Initialize complete admin account for the Enterprise Platform.
Creates admin in both Django and Keycloak.

Usage:
    python init_admin_account.py [--username admin] [--password YOUR_PASSWORD] [--email admin@example.com]
"""
import os
import sys
import django
import argparse
import requests
import json
from urllib.parse import urljoin

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.contrib.auth.models import User
from rbac.models import UserProfile, Role, Department


class AdminInitializer:
    def __init__(self):
        from django.conf import settings
        self.keycloak_url = settings.KEYCLOAK_SERVER_URL.rstrip('/')
        self.realm = settings.KEYCLOAK_REALM
        self.client_id = settings.KEYCLOAK_CLIENT_ID
        self.client_secret = settings.KEYCLOAK_CLIENT_SECRET

    def create_django_admin(self, username, email, password, first_name='Admin', last_name='User'):
        """Create admin user and profile in Django"""
        print(f"\n📝 Creating Django admin user: {username}")
        
        try:
            # Create Django user
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_staff': False,  # Not Django admin, but app admin
                    'is_superuser': False,
                }
            )
            
            if created:
                user.set_password(password)
                user.save()
                print(f"   ✓ Django user created: {username}")
            else:
                print(f"   ℹ Django user already exists: {username}")
                # Update password if user exists
                user.set_password(password)
                user.save()
                print(f"   ✓ Password updated for: {username}")
            
            # Create UserProfile
            admin_role = Role.objects.get(code='ADMIN')
            profile, profile_created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': admin_role,
                    'department': None,  # ADMIN has no department
                }
            )
            
            if profile_created:
                print(f"   ✓ UserProfile created with ADMIN role")
            else:
                print(f"   ℹ UserProfile already exists")
            
            return user, True
            
        except Exception as e:
            print(f"   ✗ Error creating Django admin: {e}")
            return None, False

    def get_service_account_token(self):
        """Get service account token using client credentials"""
        print(f"\n🔐 Obtaining Keycloak service account token...")
        
        token_url = urljoin(self.keycloak_url, f'/realms/{self.realm}/protocol/openid-connect/token')
        payload = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        
        try:
            response = requests.post(token_url, data=payload)
            if response.status_code == 200:
                token = response.json().get('access_token')
                print(f"   ✓ Service account token obtained")
                return token
            else:
                print(f"   ✗ Failed to get token: {response.status_code}")
                print(f"      {response.text[:200]}")
                return None
        except Exception as e:
            print(f"   ✗ Error: {e}")
            return None

    def create_keycloak_user(self, username, email, password, first_name, last_name, token=None):
        """Create user in Keycloak"""
        print(f"\n👤 Creating Keycloak user: {username}")
        
        if not token:
            token = self.get_service_account_token()
            if not token:
                # Try using the realm client token endpoint
                token = self._get_direct_token(username, password)
        
        if not token:
            print(f"   ⚠ Warning: Cannot create Keycloak user (no token)")
            return False

        url = urljoin(self.keycloak_url, f'/admin/realms/{self.realm}/users')
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        user_data = {
            'username': username,
            'email': email,
            'firstName': first_name,
            'lastName': last_name,
            'enabled': True,
            'emailVerified': True,
        }
        
        try:
            response = requests.post(url, json=user_data, headers=headers)
            
            if response.status_code == 201:
                print(f"   ✓ Keycloak user created")
                location = response.headers.get('Location', '')
                user_id = location.split('/')[-1] if location else 'unknown'
                
                # Set password
                self._set_keycloak_password(user_id, password, token)
                return True
                
            elif response.status_code == 409:
                print(f"   ℹ User already exists in Keycloak")
                return True
            else:
                print(f"   ✗ Failed to create Keycloak user: {response.status_code}")
                error_detail = response.json() if response.text else response.text
                print(f"      {str(error_detail)[:200]}")
                return False
                
        except Exception as e:
            print(f"   ✗ Error: {e}")
            return False

    def _set_keycloak_password(self, user_id, password, token):
        """Set password for Keycloak user"""
        url = urljoin(self.keycloak_url, f'/admin/realms/{self.realm}/users/{user_id}/reset-password')
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'type': 'password',
            'temporary': False,
            'value': password,
        }
        
        try:
            response = requests.put(url, json=payload, headers=headers)
            if response.status_code == 204:
                print(f"   ✓ Keycloak password set")
                return True
            else:
                print(f"   ⚠ Failed to set password: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ⚠ Error setting password: {e}")
            return False

    def _get_direct_token(self, username, password):
        """Try to get token directly (after creating user)"""
        # This would only work if the user already exists
        return None

    def test_login(self, username, password):
        """Test if admin can login"""
        print(f"\n🧪 Testing admin login...")
        
        token_url = urljoin(self.keycloak_url, f'/realms/{self.realm}/protocol/openid-connect/token')
        payload = {
            'grant_type': 'password',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'username': username,
            'password': password,
        }
        
        try:
            response = requests.post(token_url, data=payload)
            if response.status_code == 200:
                print(f"   ✓ Login successful!")
                data = response.json()
                print(f"   ✓ Access token: {data.get('access_token', '')[:50]}...")
                return True
            else:
                print(f"   ✗ Login failed: {response.status_code}")
                error_data = response.json() if response.text else {}
                print(f"      {error_data.get('error_description', response.text[:200])}")
                return False
        except Exception as e:
            print(f"   ✗ Error: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='Initialize admin account for Enterprise Platform')
    parser.add_argument('--username', default='admin', help='Admin username (default: admin)')
    parser.add_argument('--password', default=None, help='Admin password (will prompt if not provided)')
    parser.add_argument('--email', default='admin@example.com', help='Admin email')
    parser.add_argument('--first-name', default='Admin', help='Admin first name')
    parser.add_argument('--last-name', default='User', help='Admin last name')
    
    args = parser.parse_args()
    
    # Get password if not provided
    if not args.password:
        import getpass
        args.password = getpass.getpass("Enter admin password: ")
    
    print("\n" + "="*70)
    print("ENTERPRISE PLATFORM - ADMIN ACCOUNT INITIALIZATION")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  Username: {args.username}")
    print(f"  Email: {args.email}")
    print(f"  Name: {args.first_name} {args.last_name}")
    
    initializer = AdminInitializer()
    
    # Step 1: Create Django admin
    user, django_ok = initializer.create_django_admin(
        args.username,
        args.email,
        args.password,
        args.first_name,
        args.last_name
    )
    
    if not django_ok:
        print("\n✗ Failed to create Django admin")
        return 1
    
    # Step 2: Create Keycloak user
    keycloak_ok = initializer.create_keycloak_user(
        args.username,
        args.email,
        args.password,
        args.first_name,
        args.last_name
    )
    
    # Step 3: Test login
    print("\n" + "-"*70)
    login_ok = initializer.test_login(args.username, args.password)
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Django Admin:   {'✓' if django_ok else '✗'}")
    print(f"Keycloak User:  {'✓' if keycloak_ok else '⚠'} (may require fallback)")
    print(f"Login Test:     {'✓' if login_ok else '✗'}")
    
    if django_ok:
        print(f"\n✓ Admin account ready!")
        print(f"\nLogin credentials:")
        print(f"  Username: {args.username}")
        print(f"  Password: [as provided]")
        print(f"\nAPI Endpoint:")
        print(f"  POST http://localhost:8000/api/auth/login/")
        print(f"  Payload: {{'username': '{args.username}', 'password': '[password]'}}")
    else:
        print("\n✗ Failed to create admin account")
        return 1
    
    print("="*70 + "\n")
    
    return 0 if (django_ok and login_ok or keycloak_ok) else 1


if __name__ == '__main__':
    sys.exit(main())
