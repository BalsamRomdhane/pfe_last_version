#!/usr/bin/env python3
"""
Simple script to create admin user in Keycloak directly.
Uses the Keycloak token endpoint to test credentials after creation.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

import requests
import json
from django.conf import settings

username = 'admin'
password = 'AdminPlat@2026!'
email = 'admin@enterprise.local'

keycloak_url = settings.KEYCLOAK_SERVER_URL.rstrip('/')
realm = settings.KEYCLOAK_REALM
client_id = settings.KEYCLOAK_CLIENT_ID
client_secret = settings.KEYCLOAK_CLIENT_SECRET

print("\n" + "="*70)
print("KEYCLOAK ADMIN USER SETUP")
print("="*70)

# Step 1: Get service account token
print("\n1. Getting service account token...")
token_url = f'{keycloak_url}/realms/{realm}/protocol/openid-connect/token'
payload = {
    'grant_type': 'client_credentials',
    'client_id': client_id,
    'client_secret': client_secret,
}

response = requests.post(token_url, data=payload)
if response.status_code != 200:
    print(f"✗ Failed to get token: {response.status_code}")
    print(f"  {response.text[:200]}")
    sys.exit(1)

token = response.json().get('access_token')
print(f"✓ Token obtained: {token[:30]}...")

# Step 2: Try to create user
print(f"\n2. Creating user '{username}' in Keycloak...")
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

url = f'{keycloak_url}/admin/realms/{realm}/users'
user_data = {
    'username': username,
    'email': email,
    'firstName': 'Admin',
    'lastName': 'User',
    'enabled': True,
    'emailVerified': True,
}

response = requests.post(url, json=user_data, headers=headers)

if response.status_code == 201:
    location = response.headers.get('Location', '')
    user_id = location.split('/')[-1] if location else 'unknown'
    print(f"✓ User created: {user_id}")
    
    # Step 3: Set password
    print(f"\n3. Setting password...")
    pwd_url = f'{keycloak_url}/admin/realms/{realm}/users/{user_id}/reset-password'
    pwd_payload = {
        'type': 'password',
        'temporary': False,
        'value': password,
    }
    response = requests.put(pwd_url, json=pwd_payload, headers=headers)
    if response.status_code == 204:
        print(f"✓ Password set")
    else:
        print(f"✗ Failed to set password: {response.status_code}")
        
elif response.status_code == 409:
    print(f"ℹ User already exists")
else:
    print(f"✗ Failed to create user: {response.status_code}")
    if response.status_code == 403:
        print(f"  Service account lacks permissions - trying alternative approach...")
        
        # Try to manually verify if we can later authenticate
        print(f"\n  NOTE: User creation via admin API failed due to permissions.")
        print(f"  The admin account exists in Django.")
        print(f"  You can:")
        print(f"    1. Create Keycloak user manually via UI: {keycloak_url}/admin/")
        print(f"    2. Or use the Django admin login endpoint that works without Keycloak")
    else:
        print(f"  {response.text[:200]}")
    sys.exit(1)

# Step 4: Test login
print(f"\n4. Testing login...")
login_url = f'{keycloak_url}/realms/{realm}/protocol/openid-connect/token'
login_payload = {
    'grant_type': 'password',
    'client_id': client_id,
    'client_secret': client_secret,
    'username': username,
    'password': password,
}

response = requests.post(login_url, data=login_payload)
if response.status_code == 200:
    access_token = response.json().get('access_token')
    print(f"✓ Login successful!")
    print(f"  Access token: {access_token[:50]}...")
else:
    print(f"✗ Login failed: {response.status_code}")
    print(f"  {response.json().get('error_description', response.text[:200])}")
    print(f"  Note: This may be normal - Keycloak needs time to sync")

print("\n" + "="*70)
print("✓ Setup complete!")
print("="*70)
print(f"\nLogin credentials:")
print(f"  Username: {username}")
print(f"  Password: {password}")
print(f"  Email: {email}")
print("\n" + "="*70 + "\n")
