#!/usr/bin/env python3
"""
Script to create test users in Keycloak for development/testing.
Requires admin credentials to create users in the realm.
"""
import requests
import sys

KEYCLOAK_SERVER_URL = 'http://localhost:8081'
REALM = 'iso9001-realm'
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin'

# Test users to create (password will be set to same as username)
TEST_USERS = [
    {
        'username': 'admin1',
        'email': 'admin1@example.com',
        'firstName': 'Admin',
        'lastName': 'User',
    },
    {
        'username': 'teamlead1',
        'email': 'teamlead1@example.com',
        'firstName': 'Team',
        'lastName': 'Lead',
    },
    {
        'username': 'employee1',
        'email': 'employee1@example.com',
        'firstName': 'Employee',
        'lastName': 'One',
    },
    {
        'username': 'employee2',
        'email': 'employee2@example.com',
        'firstName': 'Employee',
        'lastName': 'Two',
    },
]


def get_admin_token():
    """Get admin token from master realm"""
    token_url = f'{KEYCLOAK_SERVER_URL}/realms/master/protocol/openid-connect/token'
    payload = {
        'grant_type': 'password',
        'client_id': 'admin-cli',
        'username': ADMIN_USERNAME,
        'password': ADMIN_PASSWORD,
    }
    response = requests.post(token_url, data=payload)
    if response.status_code != 200:
        print(f'ERROR: Failed to get admin token: {response.status_code} {response.text}')
        sys.exit(1)
    return response.json().get('access_token')


def create_user(token, user_data):
    """Create a user in Keycloak"""
    url = f'{KEYCLOAK_SERVER_URL}/admin/realms/{REALM}/users'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    user_payload = {
        'username': user_data['username'],
        'email': user_data['email'],
        'firstName': user_data['firstName'],
        'lastName': user_data['lastName'],
        'enabled': True,
        'requiredActions': ['UPDATE_PASSWORD'],
    }
    
    response = requests.post(url, json=user_payload, headers=headers)
    
    if response.status_code == 201:
        user_id = response.headers.get('Location', '').split('/')[-1]
        print(f'✓ Created user: {user_data["username"]} (ID: {user_id})')
        
        # Set password
        set_password(token, user_id, user_data['username'])
        return user_id
    elif response.status_code == 409:
        print(f'⚠ User already exists: {user_data["username"]}')
        # Get existing user ID
        get_url = f'{KEYCLOAK_SERVER_URL}/admin/realms/{REALM}/users'
        get_headers = {'Authorization': f'Bearer {token}'}
        get_response = requests.get(get_url, params={'username': user_data['username'], 'exact': 'true'}, headers=get_headers)
        if get_response.status_code == 200:
            users = get_response.json()
            return users[0]['id'] if users else None
        return None
    else:
        print(f'✗ Failed to create user {user_data["username"]}: {response.status_code} {response.text}')
        return None


def set_password(token, user_id, password):
    """Set user password"""
    url = f'{KEYCLOAK_SERVER_URL}/admin/realms/{REALM}/users/{user_id}/reset-password'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'type': 'password',
        'temporary': False,  # Not temporary - can login immediately
        'value': password,
    }
    
    response = requests.put(url, json=payload, headers=headers)
    if response.status_code == 204:
        print(f'  ✓ Password set for {user_id}')
    else:
        print(f'  ✗ Failed to set password: {response.status_code} {response.text}')


def main():
    print('Creating test users in Keycloak...')
    print(f'Server: {KEYCLOAK_SERVER_URL}')
    print(f'Realm: {REALM}')
    print()
    
    # Get admin token
    print('1. Authenticating with admin credentials...')
    try:
        token = get_admin_token()
        print('✓ Admin token obtained')
    except Exception as e:
        print(f'✗ Failed to get admin token: {e}')
        sys.exit(1)
    
    print()
    print('2. Creating test users...')
    for user_data in TEST_USERS:
        create_user(token, user_data)
    
    print()
    print('Test users created successfully!')
    print()
    print('You can now login with:')
    for user in TEST_USERS:
        print(f'  Username: {user["username"]}, Password: {user["username"]}')


if __name__ == '__main__':
    main()
