"""
Migration 0004 — Fix NOT NULL classification fields that are missing DB-level defaults.

Context
-------
Migration 0003 added classification_source (VARCHAR NOT NULL) and
classification_rules_matched (JSONB NOT NULL) without a database-level default.
Django removes column defaults after applying AddField migrations for performance,
leaving PostgreSQL with bare NOT NULL columns.  Any INSERT that omits these fields
raises IntegrityError.

This migration adds explicit DB-level defaults so the columns accept INSERTs
that do not supply a value (matching the Django model's default='' / default=list).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0003_documentsecurityanalysis_classification_fields'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                # Set DB-level default for the VARCHAR column
                "ALTER TABLE security_documentsecurityanalysis "
                "ALTER COLUMN classification_source SET DEFAULT ''",

                # Set DB-level default for the JSONB column
                "ALTER TABLE security_documentsecurityanalysis "
                "ALTER COLUMN classification_rules_matched SET DEFAULT '[]'::jsonb",

                # Back-fill any existing NULL rows (shouldn't exist, but be safe)
                "UPDATE security_documentsecurityanalysis "
                "SET classification_source = '' "
                "WHERE classification_source IS NULL",

                "UPDATE security_documentsecurityanalysis "
                "SET classification_rules_matched = '[]'::jsonb "
                "WHERE classification_rules_matched IS NULL",
            ],
            reverse_sql=[
                "ALTER TABLE security_documentsecurityanalysis "
                "ALTER COLUMN classification_source DROP DEFAULT",
                "ALTER TABLE security_documentsecurityanalysis "
                "ALTER COLUMN classification_rules_matched DROP DEFAULT",
            ],
        ),
    ]
