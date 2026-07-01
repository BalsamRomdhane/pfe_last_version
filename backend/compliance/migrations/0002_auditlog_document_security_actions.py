"""
Migration 0002 — Add document security actions to compliance.AuditLog.

New action choices added (Phase 8):
  VIEW              — document opened for inline viewing
  DOWNLOAD          — document downloaded (with optional watermark)
  DECRYPT           — document decrypted in memory (for view or download)
  INTEGRITY_CHECK   — document SHA-256 integrity verified
  ENCRYPT           — document encrypted by the security pipeline
  SECURITY_ANALYSIS — security analysis (PII/secrets/risk) run on document

These choices extend the existing Action TextChoices without modifying
any existing row. The max_length=32 already accommodates all new values.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compliance', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(
                choices=[
                    # ── Existing actions (unchanged) ──────────────────────────
                    ('CREATE',         'Create'),
                    ('UPDATE',         'Update'),
                    ('DELETE',         'Delete'),
                    ('SOFT_DELETE',    'Soft Delete'),
                    ('VALIDATE',       'Validate'),
                    ('APPROVE',        'Approve'),
                    ('REJECT',         'Reject'),
                    ('STATUS_CHANGE',  'Status Change'),
                    ('VERSION_CREATE', 'Version Create'),
                    ('RESTORE',        'Restore'),
                    ('REVIEW',         'Review'),
                    ('RISK_ACCEPT',    'Risk Accept'),
                    ('RISK_MITIGATE',  'Risk Mitigate'),
                    ('EXPORT',         'Export'),
                    # ── Phase 8 — Document security actions ───────────────────
                    ('VIEW',              'Document Viewed'),
                    ('DOWNLOAD',          'Document Downloaded'),
                    ('DECRYPT',           'Document Decrypted'),
                    ('INTEGRITY_CHECK',   'Integrity Check'),
                    ('ENCRYPT',           'Document Encrypted'),
                    ('SECURITY_ANALYSIS', 'Security Analysis'),
                ],
                max_length=32,
            ),
        ),
    ]
