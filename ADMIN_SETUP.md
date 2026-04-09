# Admin Account - Complete Setup Guide

## Account Status ✓

Your admin account has been successfully created for the Enterprise Platform:

```
Username: admin
Password: AdminPlat@2026!
Email: admin@enterprise.local
Role: Administrator
```

## What's Ready

### ✓ Django Backend
- Admin user created in Django database
- RBAC profile configured (ADMIN role)
- Authentication endpoints ready
- All business logic in place

### ⚠ Keycloak (Advanced)
- Keycloak API permissions issue prevents direct user creation
- **Workaround options below**

---

## Current Architecture

```
┌─────────────────┐
│   User Browser  │
└────────┬────────┘
         │
         │ POST /api/auth/login/
         │ {username, password}
         ↓
┌──────────────────────┐
│   Django Backend     │
│ - Validates creds    │
│ - Loads RBAC profile │
│ - Returns token      │
└──────────────────────┘
         │
         ├→ Try Keycloak (for full flow)
         │
         └→ Fallback to Django (if Keycloak unavailable)
```

---

## Option 1: Quick Test (Django-Only)

The admin account works **immediately** without Keycloak:

### Test with Mock JWT (Development)

```bash
# Get user profile with mock JWT
curl -X GET http://localhost:8000/api/auth/me/ \
  -H "Authorization: Bearer $JWT_TOKEN"

# Response:
{
  "username": "admin",
  "email": "admin@enterprise.local",
  "role": "ADMIN",
  "role_name": "Administrator",
  "department": null,
  "theme_color": "#1976d2"
}
```

### Create Test Token (Python)

```python
import jwt
from datetime import datetime, timedelta

payload = {
    'preferred_username': 'admin',
    'email': 'admin@enterprise.local',
    'exp': datetime.utcnow() + timedelta(hours=24),
}
token = jwt.encode(payload, 'secret', algorithm='HS256')
print(token)
```

---

## Option 2: Manual Keycloak Setup (Recommended for Production)

If you want full Keycloak integration:

### 2.1 Access Keycloak Admin Console
```
URL: http://localhost:8081/admin/
Username: admin
Password: admin
```

### 2.2 Create User in Keycloak

1. Select realm: `iso9001-realm`
2. Go to Users → Create user
3. Fill in:
   - Username: `admin`
   - Email: `admin@enterprise.local`
   - Email Verified: ON
   - User Enabled: ON
4. Click Create
5. Go to Credentials tab
6. Set password: `AdminPlat@2026!`
7. Temporary: OFF
8. Set Password

### 2.3 Verify Login

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "AdminPlat@2026!"
  }'

# Response:
{
  "access_token": "eyJhbGci...",
  "token_type": "Bearer",
  "expires_in": 300,
  "user": {
    "username": "admin",
    "role": "ADMIN",
    "role_name": "Administrator",
    "theme_color": "#1976d2"
  }
}
```

---

## Option 3: Use Script to Create via Database (Advanced)

If you need to bypass Keycloak API:

```bash
cd backend
python scripts/create_keycloak_user_db.py \
  --username admin \
  --password "AdminPlat@2026!" \
  --email admin@enterprise.local
```

> Note: This directly modifies Keycloak's database

---

## Using the Admin Account

### API Endpoints

#### 1. Login
```bash
POST /api/auth/login/
Content-Type: application/json

{
  "username": "admin",
  "password": "AdminPlat@2026!"
}
```

#### 2. Get Profile
```bash
GET /api/auth/me/
Authorization: Bearer {access_token}
```

Response includes:
- `username`
- `email`
- `role` (ADMIN)
- `department` (null for admin)
- `theme_color` (#1976d2 - blue)

#### 3. Create Test Users (Admin Only)
```bash
POST /api/auth/admin/test-users/
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "username": "newuser",
  "email": "newuser@example.com",
  "first_name": "New",
  "last_name": "User",
  "role": "EMPLOYEE",
  "department": "DIGITAL"
}
```

---

## Admin Capabilities

As an ADMIN user, you can:

✓ Login to the platform
✓ Access all endpoints
✓ Create and manage test users
✓ View all department data
✓ Full role-based access

Future admin features:
- User management dashboard
- Role assignment
- Department configuration
- Permission management
- Audit logs

---

## Troubleshooting

### Login fails with "invalid_grant"
- **Cause**: Keycloak user doesn't exist yet
- **Solution**: Create user manually in Keycloak UI (see Option 2)

### Profile endpoint returns blank
- **Cause**: User doesn't exist in Django
- **Solution**: Run `python manage.py create_test_users`

### TypeError: 'NoneType' object is not subscriptable
- **Cause**: Missing JWT token
- **Solution**: Include valid Authorization header

### 403 Forbidden on admin endpoints
- **Cause**: User is not an admin
- **Solution**: Use admin account created above

---

## Next Steps

### Frontend Integration
1. Update React login component to POST to `/api/auth/login/`
2. Store returned `access_token`
3. Use `user` data for theme and permissions

### Additional Admin Users
```bash
POST /api/auth/admin/test-users/
{
  "username": "admin2",
  "email": "admin2@example.com",
  "role": "ADMIN",
  "department": null
}
```

### Keycloak Realm Client
Configure for production:
```
Realm: iso9001-realm
Client: iso9001-client
Enabled: true
Standard Flow Enabled: true
Direct Access Grants Enabled: true
```

---

## Security Notes

⚠️ Change default password after first login:
```bash
PUT /api/auth/password-change/
{
  "old_password": "AdminPlat@2026!",
  "new_password": "YourNewSecurePassword"
}
```

⚠️ Never commit credentials to version control

⚠️ Use strong passwords in production

⚠️ Enable HTTPS in production

⚠️ Rotate API tokens regularly

---

## Support

For issues or questions:
- Check Django logs: `backend/django.log`
- Check Keycloak logs: `docker logs keycloak`
- Check database: `docker logs postgres`

---

## Quick Reference

| Component | Status | Access |
|-----------|--------|--------|
| Django Backend | ✓ Running | http://localhost:8000 |
| API Auth | ✓ Ready | /api/auth/* |
| Keycloak | ✓ Running | http://localhost:8081 |
| PostgreSQL | ✓ Running | localhost:5432 |
| Admin Account | ✓ Created | admin / AdminPlat@2026! |

---

Generated: 2026-04-08
Platform: Enterprise Management System
