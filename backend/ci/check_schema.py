"""Affiche les colonnes reelles de api_mlopsconfig dans PostgreSQL."""
import os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()
from django.db import connection
with connection.cursor() as c:
    c.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'api_mlopsconfig'
        ORDER BY ordinal_position
    """)
    print('=== api_mlopsconfig colonnes reelles ===')
    for r in c.fetchall():
        print(' ', r)

    c.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'api_trainingjob'
        ORDER BY ordinal_position
    """)
    print('=== api_trainingjob colonnes reelles ===')
    for r in c.fetchall():
        print(' ', r)
