"""
Migration 0003 — Add classification audit fields to DocumentSecurityAnalysis.

New fields
----------
  classification_source          VARCHAR(64)  — name of the winning classification rule
  classification_rules_matched   JSONField    — list of all rules that fired

These fields complement the existing `confidentiality_level` and
`confidentiality_score` fields.  All existing rows get safe defaults
(empty string / empty list) — no data migration required.

No existing field is modified.
No existing endpoint is affected.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0002_rename_security_do_risk_le_idx_security_do_risk_le_46e0fe_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='documentsecurityanalysis',
            name='classification_source',
            field=models.CharField(
                max_length=64,
                blank=True,
                default='',
                help_text='Name of the classification rule that determined the final level.',
                verbose_name='Classification source',
            ),
        ),
        migrations.AddField(
            model_name='documentsecurityanalysis',
            name='classification_rules_matched',
            field=models.JSONField(
                default=list,
                blank=True,
                help_text='List of all classification rule names that fired.',
                verbose_name='Matched classification rules',
            ),
        ),
    ]
