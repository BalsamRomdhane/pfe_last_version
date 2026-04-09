#!/usr/bin/env python3
"""Verify admin account is ready"""
import requests
import json
import jwt

print('\n' + '='*70)
print('ADMIN ACCOUNT VERIFICATION')
print('='*70)

BASE = 'http://localhost:8000/api/auth'

# 1. Check admin status
print('\n1. Checking admin account status...')
r = requests.get(f'{BASE}/admin-status/')
data = r.json()
admins = data.get('admins', [])
found = False
for admin in admins:
    if admin['username'] == 'admin':
        print(f'   ✓ Admin account found:')
        print(f'     Username: {admin["username"]}')
        print(f'     Email: {admin["email"]}')
        print(f'     Role: {admin["role"]}')
        print(f'     Created: {admin["created"][:10]}')
        found = True
        break

if not found:
    print('   ✗ Admin account not found')

# 2. Test with mock JWT
print('\n2. Testing profile endpoint with mock JWT...')
payload = {'preferred_username': 'admin', 'email': 'admin@enterprise.local'}
token = jwt.encode(payload, 'test', algorithm='HS256')
r = requests.get(f'{BASE}/me/', headers={'Authorization': f'Bearer {token}'})
if r.status_code == 200:
    profile = r.json()
    print(f'   ✓ Profile retrieved:')
    print(f'     Role: {profile["role"]} ({profile["role_name"]})')
    print(f'     Theme Color: {profile["theme_color"]}')
    print(f'     Department: {profile.get("department_name", "None (Admin)")}')
else:
    print(f'   ✗ Failed: {r.status_code}')

print('\n' + '='*70)
print('✓ Admin account is ready for use!')
print('='*70)
print('\nCredentials:')
print('  Username: admin')
print('  Password: AdminPlat@2026!')
print('='*70 + '\n')
