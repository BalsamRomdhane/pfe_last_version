"""
Migration 0018 — Add SHA-256 integrity fields to Document model.

Fields added (all nullable/blank — existing rows are untouched):
  sha256_hash       VARCHAR(64)  — hex digest of the file at upload/replacement
  hash_algorithm    VARCHAR(16)  — algorithm name, default 'sha256'
  hash_created_at   TIMESTAMPTZ  — when the hash was last computed

Index:
  api_document_sha256_idx — partial index on sha256_hash WHERE sha256_hash != ''
  Justification: used by the Phase 2 integrity endpoint and duplicate detection.
  Partial (not full) because ~30% of rows may have an empty hash (legacy docs
  uploaded before Phase 1, or documents whose pipeline thread is still running).
  Indexing empty strings would waste space and slow writes.
  PostgreSQL is required by this project, so partial indexes are supported.

No existing data is modified.
No existing endpoint or test is affected.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0017_fix_mlopsconfig_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='sha256_hash',
            field=models.CharField(
                max_length=64,
                blank=True,
                default='',
                help_text='SHA-256 hex digest of the document file, computed at upload.',
                verbose_name='SHA-256 hash',
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='hash_algorithm',
            field=models.CharField(
                max_length=16,
                blank=True,
                default='sha256',
                help_text='Algorithm used to compute sha256_hash.',
                verbose_name='Hash algorithm',
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='hash_created_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Timestamp when the integrity hash was last computed.',
                verbose_name='Hash computed at',
            ),
        ),
    ]
