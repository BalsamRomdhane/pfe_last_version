"""
Migration 0021 — Add database-level DEFAULT values for integrity and encryption fields.

Problem
-------
Migrations 0018 and 0019 added NOT NULL columns (sha256_hash, hash_algorithm,
encrypted, encryption_iv, encrypted_key_id) with Python-side defaults only.
Django does not write DB-level DEFAULT clauses for CharField/BooleanField by
default, so if the server process was started *before* these migrations ran,
its in-memory Document model is missing these fields entirely.  The INSERT
Django generates omits those columns, and PostgreSQL raises:

    IntegrityError: null value in column "sha256_hash" violates not-null constraint

Fix
---
Use ALTER TABLE … ALTER COLUMN … SET DEFAULT to add the PostgreSQL-level
default for each affected column.  After this migration runs, Postgres will
fill in the correct defaults even when Django omits the columns from the INSERT
(stale server process or any other code path that bypasses the ORM defaults).

After a server restart the model will be fully up to date and these DB defaults
become a belt-and-suspenders safety net rather than a workaround.

No data is modified.  No existing endpoint or test is affected.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0020_alter_document_encrypted_key_id_and_more'),
    ]

    operations = [
        # ── Phase 1 / 0018 columns ────────────────────────────────────────────
        migrations.RunSQL(
            sql="ALTER TABLE api_document ALTER COLUMN sha256_hash SET DEFAULT '';",
            reverse_sql="ALTER TABLE api_document ALTER COLUMN sha256_hash DROP DEFAULT;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE api_document ALTER COLUMN hash_algorithm SET DEFAULT 'sha256';",
            reverse_sql="ALTER TABLE api_document ALTER COLUMN hash_algorithm DROP DEFAULT;",
        ),
        # hash_created_at is nullable — no DEFAULT needed

        # ── Phase 4 / 0019 columns ────────────────────────────────────────────
        migrations.RunSQL(
            sql="ALTER TABLE api_document ALTER COLUMN encrypted SET DEFAULT false;",
            reverse_sql="ALTER TABLE api_document ALTER COLUMN encrypted DROP DEFAULT;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE api_document ALTER COLUMN encryption_iv SET DEFAULT '';",
            reverse_sql="ALTER TABLE api_document ALTER COLUMN encryption_iv DROP DEFAULT;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE api_document ALTER COLUMN encrypted_key_id SET DEFAULT '';",
            reverse_sql="ALTER TABLE api_document ALTER COLUMN encrypted_key_id DROP DEFAULT;",
        ),
    ]
