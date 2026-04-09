#!/usr/bin/env python3
"""
Create Keycloak user by direct database insertion (bypasses API permission issues).
Works when Keycloak admin API is restricted.
"""
import os
import sys
import uuid
import hashlib
import base64
import json
from datetime import datetime

# Fix encoding issues on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Try to connect to PostgreSQL
try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("Error: psycopg2 not installed")
    print("Install with: pip install psycopg2-binary")
    sys.exit(1)


class KeycloakDBInitializer:
    def __init__(self, host='localhost', port=5432, database='enterprise_db',
                 user='postgres', password='password', realm='iso9001-realm'):
        self.host = host
        self.port = port
        self.database = database
        self.db_user = user
        self.db_password = password
        self.realm_name = realm
        self.conn = None
        self.realm_id = None

    def connect(self):
        """Connect to PostgreSQL"""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.db_user,
                password=self.db_password
            )
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            print(f"✓ Connected to {self.database}")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False

    def get_realm_id(self):
        """Get Keycloak realm ID"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM keycloak_realm WHERE name = %s", (self.realm_name,))
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                self.realm_id = result[0]
                print(f"✓ Found realm: {self.realm_id}")
                return self.realm_id
            else:
                print(f"✗ Realm not found: {self.realm_name}")
                return None
        except Exception as e:
            print(f"✗ Error getting realm: {e}")
            return None

    def hash_password_pbkdf2(self, password, iterations=27500):
        """Hash password using PBKDF2-SHA256 like Keycloak"""
        salt = os.urandom(16)
        # Generate key using PBKDF2
        key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
        # Format: $PBKDF2$iterations$salt_hex$key_hex
        return f"$PBKDF2$27500${salt.hex()}${key.hex()}"

    def create_user(self, username, email, first_name, last_name):
        """Create user in Keycloak database"""
        if not self.realm_id:
            print("✗ No realm ID")
            return False

        user_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp() * 1000)

        try:
            cursor = self.conn.cursor()
            
            # Check if user already exists
            cursor.execute(
                "SELECT id FROM user_entity WHERE realm_id = %s AND username = %s",
                (self.realm_id, username)
            )
            if cursor.fetchone():
                print(f"ℹ User already exists: {username}")
                cursor.close()
                return True

            # Insert user
            cursor.execute("""
                INSERT INTO user_entity 
                (id, realm_id, username, created_timestamp, email, email_verified,
                 enabled, first_name, last_name, not_before, otp_enabled, totp_enabled)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id, self.realm_id, username, timestamp, email, True,
                True, first_name, last_name, 0, False, False
            ))
            
            print(f"✓ User created: {username}")
            cursor.close()
            return True

        except Exception as e:
            print(f"✗ Error creating user: {e}")
            return False

    def set_password(self, username, password):
        """Set password for user"""
        try:
            cursor = self.conn.cursor()
            
            # Get user ID
            cursor.execute(
                "SELECT id FROM user_entity WHERE realm_id = %s AND username = %s",
                (self.realm_id, username)
            )
            result = cursor.fetchone()
            if not result:
                print(f"✗ User not found: {username}")
                cursor.close()
                return False

            user_id = result[0]

            # Hash password
            password_hash = self.hash_password_pbkdf2(password)

            # Check if credential already exists
            cursor.execute(
                "SELECT id FROM credential WHERE user_id = %s AND type = %s",
                (user_id, 'password')
            )
            credential = cursor.fetchone()

            if credential:
                # Update existing credential
                cursor.execute("""
                    UPDATE credential 
                    SET secret_data = %s
                    WHERE user_id = %s AND type = %s
                """, (
                    json.dumps({"value": password_hash}),
                    user_id, 'password'
                ))
                print(f"✓ Password updated for: {username}")
            else:
                # Create new credential
                credential_id = str(uuid.uuid4())
                timestamp = int(datetime.now().timestamp() * 1000)
                
                cursor.execute("""
                    INSERT INTO credential
                    (id, user_id, created_date, credential_data, credential_type,
                     priority, provider, secret_data, user_label)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    credential_id, user_id, timestamp,
                    '{}', 'password',
                    10, 'keycloak-cd',
                    json.dumps({"value": password_hash}),
                    None
                ))
                print(f"✓ Password set for: {username}")

            cursor.close()
            return True

        except Exception as e:
            print(f"✗ Error setting password: {e}")
            return False

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("✓ Database connection closed")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Create Keycloak user in database (when admin API is unavailable)'
    )
    parser.add_argument('--username', default='admin', help='Username')
    parser.add_argument('--password', default='AdminPlat@2026!', help='Password')
    parser.add_argument('--email', default='admin@enterprise.local', help='Email')
    parser.add_argument('--first-name', default='Admin', help='First name')
    parser.add_argument('--last-name', default='User', help='Last name')
    parser.add_argument('--host', default='localhost', help='PostgreSQL host')
    parser.add_argument('--port', type=int, default=5432, help='PostgreSQL port')
    parser.add_argument('--db', default='enterprise_db', help='Database name')
    parser.add_argument('--db-user', default='postgres', help='Database user')
    parser.add_argument('--db-password', default='password', help='Database password')
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("KEYCLOAK DATABASE USER INITIALIZATION")
    print("="*70)
    
    initializer = KeycloakDBInitializer(
        host=args.host,
        port=args.port,
        database=args.db,
        user=args.db_user,
        password=args.db_password
    )
    
    # Connect to database
    if not initializer.connect():
        return 1
    
    # Get realm
    if not initializer.get_realm_id():
        return 1
    
    # Create user
    if not initializer.create_user(args.username, args.email, args.first_name, args.last_name):
        return 1
    
    # Set password
    if not initializer.set_password(args.username, args.password):
        return 1
    
    initializer.close()
    
    print("\n" + "="*70)
    print("✓ Keycloak user created successfully!")
    print("="*70)
    print(f"\nYou can now login with:")
    print(f"  Username: {args.username}")
    print(f"  Password: {args.password}")
    print("="*70 + "\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
