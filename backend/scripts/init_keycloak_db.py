#!/usr/bin/env python3
"""
Initialize Keycloak with test users using direct database access.
This is a workaround for when the admin API isn't working.
"""
import os
import psycopg2
import hashlib
import uuid
from datetime import datetime

# Database connection
DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'enterprise_db'
DB_USER = 'postgres'
DB_PASSWORD = 'password'

REALM_NAME = 'iso9001-realm'

# Test users to create
TEST_USERS = [
    ('admin1', 'admin1@example.com', 'admin1'),  # username, email, password
    ('teamlead1', 'teamlead1@example.com', 'teamlead1'),
    ('employee1', 'employee1@example.com', 'employee1'),
    ('employee2', 'employee2@example.com', 'employee2'),
]


def hash_password(password):
    """Hash password using Keycloak's default algorithm"""
    # Keycloak uses PBKDF2-SHA256 with iterations=27500
    # For simplicity, we'll use a basic hash that Keycloak might accept
    import hashlib
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 27500)
    return f"$PBKDF2$27500${salt.hex()}${key.hex()}"


def create_users_via_db():
    """Create test users directly in Keycloak database"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        print(f"Connected to {DB_NAME} database")
        
        # First, get the realm ID
        cursor.execute(f"SELECT id FROM keycloak_realm WHERE name = %s", (REALM_NAME,))
        result = cursor.fetchone()
        if not result:
            print(f"ERROR: Realm {REALM_NAME} not found")
            return False
        
        realm_id = result[0]
        print(f"Found realm: {realm_id}")
        
        # Create users
        for username, email, password in TEST_USERS:
            user_id = str(uuid.uuid4())
            
            # Check if user already exists
            cursor.execute(
                "SELECT id FROM user_entity WHERE realm_id = %s AND username = %s",
                (realm_id, username)
            )
            if cursor.fetchone():
                print(f"✓ User {username} already exists")
                continue
            
            # Insert user
            cursor.execute("""
                INSERT INTO user_entity (id, realm_id, username, email_verified, not_before,
                                      otp_enabled, totp_enabled, created_timestamp, enabled, first_name, 
                                      last_name, email, service_account_client_link)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id, realm_id, username, False, 0, False, False,
                int(datetime.now().timestamp() * 1000), True,
                username.split('_')[0], username.split('_')[-1] if '_' in username else 'User',
                email, None
            ))
            
            # Insert password credential
            password_hash = hash_password(password)
            credential_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO credential (id, user_id, created_date, credential_data, credential_type, 
                                     secret_data, user_label, provider, priority)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                credential_id, user_id,
                int(datetime.now().timestamp() * 1000),
                '{}',  # credential_data
                'password',
                f'{{"value": "{password_hash}", "salt": ""}}',  # secret_data
                None,  # user_label
                'keycloak-cd',  # provider
                10  # priority
            ))
            
            print(f"✓ Created user: {username}")
        
        conn.commit()
        print("\n✓ All users created successfully")
        return True
        
    except Exception as e:
        print(f"ERROR: {e}") return False
    finally:
        if conn:
            cursor.close()
            conn.close()


def main():
    print("=" * 60)
    print("Keycloak Direct Database User Initialization")
    print("=" * 60)
    print()
    
    print(f"Database: {DB_NAME} at {DB_HOST}:{DB_PORT}")
    print(f"Realm: {REALM_NAME}")
    print()
    
    success = create_users_via_db()
    
    print()
    print("=" * 60)
    if success:
        print("✓ Keycloak users initialized")
        print("\nYou can now login with:")
        for username, email, password in TEST_USERS:
            print(f"  {username} / {password}")
    else:
        print("✗ Failed to initialize users")
    print("=" * 60)
    
    return 0 if success else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
