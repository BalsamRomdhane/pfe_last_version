"""
Migration 0019 — Add AES-256-GCM encryption fields to Document model.

Fields added
------------
  encrypted         BOOLEAN   — True when the file on disk is AES-256-GCM encrypted
  encryption_iv     VARCHAR(24) — base64-encoded 12-byte GCM nonce (stored for reference)
  encrypted_at      TIMESTAMPTZ — when encryption was applied
  encrypted_key_id  VARCHAR(64) — identifies which key was used (currently always 'env_key')

All fields are nullable/blank so existing rows are untouched.
No existing data is modified.
No existing endpoint is affected.

Note on nonce storage
---------------------
The nonce is stored in the Document row for observability and key rotation
purposes. The canonical nonce used for decryption is always extracted from
the first 12 bytes of the ciphertext file (which is the source of truth).
The encryption_iv column is informational only — it is never used as the
decryption nonce to prevent desync bugs.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0018_document_integrity_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='encrypted',
            field=models.BooleanField(
                default=False,
                help_text='True when the stored file is AES-256-GCM encrypted.',
                verbose_name='Encrypted',
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='encryption_iv',
            field=models.CharField(
                max_length=24,
                blank=True,
                default='',
                help_text='Base64-encoded 12-byte GCM nonce (informational — source of truth is the file).',
                verbose_name='Encryption IV (nonce)',
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='encrypted_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Timestamp when encryption was applied.',
                verbose_name='Encrypted at',
            ),
        ),
        migrations.AddField(
            model_name='document',
            name='encrypted_key_id',
            field=models.CharField(
                max_length=64,
                blank=True,
                default='',
                help_text='Identifier of the key used for encryption (e.g. env_key, kms_key_v2).',
                verbose_name='Encryption key ID',
            ),
        ),
    ]
