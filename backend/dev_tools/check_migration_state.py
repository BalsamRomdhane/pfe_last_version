import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'enterprise_platform.settings'
django.setup()

from django.db import connection

with connection.cursor() as c:
    # 1. Colonnes reelles de api_trainingjob dans PostgreSQL
    c.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'api_trainingjob'
        ORDER BY ordinal_position
    """)
    print('=== COLONNES REELLES api_trainingjob ===')
    rows = c.fetchall()
    for row in rows:
        print(' ', row)
    col_names = [r[0] for r in rows]
    print('')
    print('log_output present dans PostgreSQL:', 'log_output' in col_names)

    # 2. Historique django_migrations pour app=api
    c.execute("""
        SELECT name, applied
        FROM django_migrations
        WHERE app = 'api'
        ORDER BY id
    """)
    print('')
    print('=== MIGRATIONS api enregistrees dans django_migrations ===')
    applied = []
    for row in c.fetchall():
        print(' ', row)
        applied.append(row[0])
    print('')
    print('0014 dans django_migrations:', '0014_trainingjob_log_output' in applied)
