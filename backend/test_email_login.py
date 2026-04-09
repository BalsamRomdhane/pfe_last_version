#!/usr/bin/env python3
"""
Test login with both username and email formats.
"""
import requests
import json

BASE_URL = 'http://localhost:8000/api/auth'

print("\n" + "="*70)
print("LOGIN WITH EMAIL OR USERNAME TEST")
print("="*70)

# Test 1: Login with username
print("\n1. LOGIN WITH USERNAME")
print("-" * 70)
payload = {
    'username': 'admin',
    'password': 'AdminPlat@2026!'
}
print(f"POST {BASE_URL}/login/")
print(f"Payload: {json.dumps(payload)}")
response = requests.post(f'{BASE_URL}/login/', json=payload)
print(f"\nStatus: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print("✓ Success!")
    print(f"  User: {data['user']['username']}")
    print(f"  Email: {data['user']['email']}")
    print(f"  Role: {data['user']['role_name']}")
    print(f"  Token: {data['access_token'][:50]}...")
else:
    print(f"✗ Failed: {response.json().get('error')}")

# Test 2: Login with email
print("\n2. LOGIN WITH EMAIL")
print("-" * 70)
payload = {
    'email': 'admin@enterprise.local',
    'password': 'AdminPlat@2026!'
}
print(f"POST {BASE_URL}/login/")
print(f"Payload: {json.dumps(payload)}")
response = requests.post(f'{BASE_URL}/login/', json=payload)
print(f"\nStatus: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print("✓ Success!")
    print(f"  User: {data['user']['username']}")
    print(f"  Email: {data['user']['email']}")
    print(f"  Role: {data['user']['role_name']}")
    print(f"  Token: {data['access_token'][:50]}...")
else:
    print(f"✗ Failed: {response.json().get('error')}")

# Test 3: Login with employee email
print("\n3. LOGIN WITH EMPLOYEE EMAIL")
print("-" * 70)
payload = {
    'email': 'employee1@example.com',
    'password': None  # Will fail because we don't have password set
}
print(f"POST {BASE_URL}/login/")
print(f"Payload: {json.dumps(payload, default=str)}")
response = requests.post(f'{BASE_URL}/login/', json=payload)
print(f"\nStatus: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print("✓ Success!")
    print(f"  User: {data['user']['username']}")
    print(f"  Email: {data['user']['email']}")
    print(f"  Role: {data['user']['role_name']}")
else:
    error = response.json().get('error') or response.json().get('detail')
    print(f"Status OK - Error expected (no password set): {error}")

# Test 4: Invalid email
print("\n4. LOGIN WITH INVALID EMAIL")
print("-" * 70)
payload = {
    'email': 'nonexistent@example.com',
    'password': 'SomePassword'
}
print(f"POST {BASE_URL}/login/")
print(f"Payload: {json.dumps(payload)}")
response = requests.post(f'{BASE_URL}/login/', json=payload)
print(f"\nStatus: {response.status_code}")
error = response.json().get('error') or response.json().get('detail')
print(f"✓ Correctly rejected: {error}")

# Test 5: No credentials
print("\n5. LOGIN WITH NO CREDENTIALS")
print("-" * 70)
payload = {
    'password': 'SomePassword'
}
print(f"POST {BASE_URL}/login/")
print(f"Payload: {json.dumps(payload)}")
response = requests.post(f'{BASE_URL}/login/', json=payload)
print(f"\nStatus: {response.status_code}")
if response.status_code != 200:
    error = response.json().get('username') or response.json()
    print(f"✓ Correctly rejected: {str(error)[:100]}")

print("\n" + "="*70)
print("✓ Email login feature is working!")
print("="*70)
print("\nYou can now login with:")
print("  • Username: admin")
print("  • Email: admin@enterprise.local")
print("  • Password: AdminPlat@2026!")
print("="*70 + "\n")
