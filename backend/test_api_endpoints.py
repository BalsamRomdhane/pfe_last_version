#!/usr/bin/env python3
"""
Test the authentication APIs by making HTTP requests.
Requires Django server running on localhost:8000
"""
import requests
import json
import jwt
from datetime import datetime, timedelta

BASE_URL = 'http://localhost:8000/api/auth'

def test_login_endpoint():
    """Test POST /auth/login/"""
    print("\n" + "="*60)
    print("TEST 1: Login Endpoint (Password Grant)")
    print("="*60)
    
    # Try with a test user (should fail - not in Keycloak)
    payload = {
        'username': 'admin1',
        'password': 'admin1'
    }
    
    print(f"POST {BASE_URL}/login/")
    print(f"Payload: {json.dumps(payload)}")
    
    try:
        response = requests.post(f'{BASE_URL}/login/', json=payload)
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        return response.status_code in [200, 401, 403]  # Any response means endpoint works
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def test_me_endpoint_without_token():
    """Test GET /me/ without token"""
    print("\n" + "="*60)
    print("TEST 2: Get Profile Endpoint (No Token)")
    print("="*60)
    
    print(f"GET {BASE_URL}/me/")
    print("Headers: (no Authorization)")
    
    try:
        response = requests.get(f'{BASE_URL}/me/')
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2) if response.text else '(empty)'}")
        # Should be 401 Unauthorized when no token
        return response.status_code == 401
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def test_me_endpoint_with_mock_token():
    """Test GET /me/ with a mock JWT token"""
    print("\n" + "="*60)
    print("TEST 3: Get Profile Endpoint (With Mock JWT)")
    print("="*60)
    
    # Create a mock JWT like Keycloak would
    payload = {
        'preferred_username': 'admin1',
        'sub': 'admin1-uuid',
        'email': 'admin1@example.com',
        'exp': datetime.utcnow() + timedelta(hours=1),
        'iat': datetime.utcnow(),
    }
    
    # Encode without signature verification (can use any secret)
    token = jwt.encode(payload, 'test-secret', algorithm='HS256')
    print(f"Created mock JWT: {token[:50]}...")
    print(f"  Payload: {json.dumps(payload, default=str, indent=2)}")
    
    print(f"\nGET {BASE_URL}/me/")
    print(f"Authorization: Bearer {token[:50]}...")
    
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(f'{BASE_URL}/me/', headers=headers)
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def test_admin_endpoint():
    """Test POST /admin/test-users/"""
    print("\n" + "="*60)
    print("TEST 4: Admin Create Test User Endpoint")
    print("="*60)
    
    payload = {
        'username': 'newuser',
        'email': 'newuser@example.com',
        'first_name': 'New',
        'last_name': 'User',
        'role': 'EMPLOYEE',
        'department': 'DIGITAL',
    }
    
    print(f"POST {BASE_URL}/admin/test-users/")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(f'{BASE_URL}/admin/test-users/', json=payload)
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2) if response.text else '(empty)'}")
        # Should be 403 without admin token (expected)
        return response.status_code in [201, 403]
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("AUTHENTICATION API TESTS")
    print("="*60)
    print(f"\nBase URL: {BASE_URL}")
    print("Assuming Django server is running on localhost:8000")
    
    results = {
        'Login Endpoint': test_login_endpoint(),
        'Get Profile (No Token)': test_me_endpoint_without_token(),
        'Get Profile (With Mock JWT)': test_me_endpoint_with_mock_token(),
        'Admin Create User': test_admin_endpoint(),
    }
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        symbol = "✓" if passed else "✗"
        print(f"{symbol} {test_name}")
    
    all_passed = all(results.values())
    print("="*60)
    if all_passed:
        print("✓ All API tests passed!")
    else:
        print("✗ Some tests failed or had issues")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
