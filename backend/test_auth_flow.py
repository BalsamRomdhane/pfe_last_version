#!/usr/bin/env python3
"""
Test script for the complete authentication flow.
Tests login, profile loading, and RBAC integration.
"""
import os
import sys
import django
import jwt
import json
import requests
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.contrib.auth.models import User
from rbac.models import UserProfile, Role, Department
from authentication.services import KeycloakService


def test_django_setup():
    """Verify Django users and profiles exist"""
    print("\n=== Test 1: Django Setup ===")
    users = User.objects.all()
    print(f"Django users: {users.count()}")
    for user in users:
        try:
            profile = user.profile
            print(f"  ✓ {user.username}: {profile.role.code} in {profile.department.code if profile.department else 'N/A'}")
        except UserProfile.DoesNotExist:
            print(f"  ✗ {user.username}: No profile")
    return users.count() > 0


def test_keycloak_connectivity():
    """Test if Keycloak is accessible"""
    print("\n=== Test 2: Keycloak Connectivity ===")
    try:
        response = requests.get('http://localhost:8081/realms/iso9001-realm')
        if response.status_code == 200:
            print("✓ Keycloak realm accessible")
            return True
        else:
            print(f"✗ Keycloak returned {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Cannot reach Keycloak: {e}")
        return False


def test_keycloak_admin_token():
    """Test if we can get admin token"""
    print("\n=== Test 3: Keycloak Admin Token ===")
    token_url = 'http://localhost:8081/realms/master/protocol/openid-connect/token'
    payload = {
        'grant_type': 'password',
        'client_id': 'admin-cli',
        'username': 'admin',
        'password': 'admin',
    }
    try:
        response = requests.post(token_url, data=payload)
        if response.status_code == 200:
            token = response.json().get('access_token')
            print("✓ Admin token obtained successfully")
            return token
        else:
            print(f"✗ Failed to get admin token: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def test_create_keycloak_user(admin_token):
    """Try to create a test user using admin token"""
    print("\n=== Test 4: Create Keycloak User ===")
    if not admin_token:
        print("⚠ Skipped - no admin token")
        return False
    
    url = 'http://localhost:8081/admin/realms/iso9001-realm/users'
    headers = {
        'Authorization': f'Bearer {admin_token}',
        'Content-Type': 'application/json'
    }
    user_data = {
        'username': 'testuser',
        'email': 'test@example.com',
        'enabled': True,
        'requiredActions': ['UPDATE_PASSWORD'],
    }
    
    try:
        response = requests.post(url, json=user_data, headers=headers)
        if response.status_code in (201, 204):
            print("✓ User created in Keycloak")
            return True
        elif response.status_code == 409:
            print("⚠ User already exists")
            return True  # User exists, that's fine for testing
        else:
            print(f"✗ Failed to create user: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_jwt_decode():
    """Test JWT encoding/decoding"""
    print("\n=== Test 5: JWT Encoding/Decoding ===")
    try:
        # Create a mock JWT like Keycloak would
        payload = {
            'preferred_username': 'admin1',
            'sub': 'admin1-uuid',
            'email': 'admin1@example.com',
            'name': 'Admin User',
            'exp': datetime.utcnow() + timedelta(hours=1),
            'iat': datetime.utcnow(),
        }
        token = jwt.encode(payload, 'secret', algorithm='HS256')
        print(f"✓ Created test JWT: {token[:50]}...")
        
        # Decode it
        decoded = jwt.decode(token, options={"verify_signature": False})
        username = decoded.get('preferred_username')
        print(f"✓ Decoded JWT, username: {username}")
        return username == 'admin1'
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_keycloak_service():
    """Test KeycloakService profile loading"""
    print("\n=== Test 6: KeycloakService Profile Loading ===")
    
    try:
        # Create a mock JWT
        payload = {
            'preferred_username': 'admin1',
            'sub': 'admin1-uuid',
            'email': 'admin1@example.com',
            'exp': datetime.utcnow() + timedelta(hours=1),
        }
        test_token = jwt.encode(payload, 'secret', algorithm='HS256')
        
        # Try to get profile
        service = KeycloakService()
        profile = service.get_user_profile(test_token)
        
        print("✓ Profile loaded successfully:")
        for key, value in profile.items():
            print(f"    {key}: {value}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_api_endpoints():
    """Test the actual API endpoints"""
    print("\n=== Test 7: API Endpoints ===")
    
    base_url = 'http://localhost:8000/api/auth'
    
    # Test login endpoint (will fail without valid Keycloak user)
    print("Testing POST /api/auth/login/ ...")
    try:
        response = requests.post(f'{base_url}/login/', json={
            'username': 'testuser',
            'password': 'testuser'
        })
        print(f"  Response: {response.status_code}")
        if response.status_code in (200, 401):
            print(f"  ✓ Endpoint responded: {response.json()}")
        else:
            print(f"  Response: {response.text[:200]}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    # Test /me endpoint without token (should fail)
    print("Testing GET /api/auth/me/ (without token) ...")
    try:
        response = requests.get(f'{base_url}/me/')
        print(f"  Response: {response.status_code} (expected 401 or similar)")
    except Exception as e:
        print(f"  Error: {e}")


def main():
    print("="*60)
    print("AUTHENTICATION FLOW TEST SUITE")
    print("="*60)
    
    results = {
        'Django Setup': test_django_setup(),
        'Keycloak Connectivity': test_keycloak_connectivity(),
    }
    
    admin_token = test_keycloak_admin_token()
    results['Keycloak Admin Token'] = admin_token is not None
    
    if admin_token:
        results['Create Keycloak User'] = test_create_keycloak_user(admin_token)
    
    results['JWT Encoding/Decoding'] = test_jwt_decode()
    results['KeycloakService Profile Loading'] = test_keycloak_service()
    
    print("\n=== Summary ===")
    for test_name, passed in results.items():
        symbol = "✓" if passed else "✗"
        print(f"{symbol} {test_name}")
    
    all_passed = all(results.values())
    print("\n" + ("="*60))
    if all_passed:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed")
    print("="*60)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
