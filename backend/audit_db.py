import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'enterprise_platform.settings'
django.setup()
from django.db import connection

with connection.cursor() as c:
    c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
    print('=== TABLES ===')
    for r in c.fetchall(): print(' ', r[0])

    c.execute("SELECT tablename, indexname FROM pg_indexes WHERE schemaname='public' ORDER BY tablename, indexname")
    print('\n=== INDEXES ===')
    for r in c.fetchall(): print(' ', r)

    c.execute("""
        SELECT conname, contype, conrelid::regclass
        FROM pg_constraint
        WHERE contype IN ('p','u','f')
        ORDER BY conrelid::regclass::text
    """)
    print('\n=== CONSTRAINTS ===')
    for r in c.fetchall(): print(' ', r)

    # Row counts
    c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    tables = [r[0] for r in c.fetchall()]
    print('\n=== ROW COUNTS ===')
    for t in sorted(tables):
        try:
            c.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"  {t}: {c.fetchone()[0]}")
        except Exception as e:
            print(f"  {t}: ERROR {e}")
