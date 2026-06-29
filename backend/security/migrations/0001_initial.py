# Generated migration for security.DocumentSecurityAnalysis
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('api', '0017_fix_mlopsconfig_data'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentSecurityAnalysis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pii_count', models.PositiveIntegerField(default=0)),
                ('pii_types', models.JSONField(blank=True, default=dict, help_text='{"EMAIL": 2, "PHONE": 1, …}')),
                ('pii_details', models.JSONField(blank=True, default=list, help_text='List of redacted PII matches with context')),
                ('secret_count', models.PositiveIntegerField(default=0)),
                ('secret_types', models.JSONField(blank=True, default=dict, help_text='{"JWT": 1, "AWS_ACCESS_KEY": 1, …}')),
                ('secret_details', models.JSONField(blank=True, default=list, help_text='List of redacted secret matches')),
                ('financial_data_detected', models.BooleanField(default=False)),
                ('employee_data_detected', models.BooleanField(default=False)),
                ('metadata_risk', models.PositiveSmallIntegerField(default=0, help_text='0–30 metadata risk contribution')),
                ('metadata_details', models.JSONField(blank=True, default=dict, help_text='Extracted document metadata')),
                ('confidentiality_level', models.CharField(
                    choices=[
                        ('PUBLIC', 'Public'), ('INTERNAL', 'Internal'),
                        ('CONFIDENTIAL', 'Confidential'), ('RESTRICTED', 'Restricted'),
                        ('SECRET', 'Secret'),
                    ],
                    default='PUBLIC', max_length=16,
                )),
                ('confidentiality_score', models.PositiveSmallIntegerField(default=0, help_text='0–100')),
                ('risk_score', models.PositiveSmallIntegerField(default=0, help_text='0–100')),
                ('risk_level', models.CharField(
                    choices=[
                        ('LOW', 'Low'), ('MEDIUM', 'Medium'),
                        ('HIGH', 'High'), ('CRITICAL', 'Critical'),
                    ],
                    default='LOW', max_length=8,
                )),
                ('score_breakdown', models.JSONField(blank=True, default=dict, help_text='Per-category score contributions')),
                ('score_explanation', models.JSONField(blank=True, default=list, help_text='Human-readable explanation list')),
                ('gdpr_status', models.CharField(
                    choices=[
                        ('OK', 'Compliant'), ('WARNING', 'Warning'),
                        ('NON_COMPLIANT', 'Non-Compliant'), ('UNKNOWN', 'Unknown'),
                    ],
                    default='UNKNOWN', max_length=16,
                )),
                ('gdpr_has_pii', models.BooleanField(default=False)),
                ('gdpr_has_sensitive', models.BooleanField(default=False)),
                ('gdpr_has_financial', models.BooleanField(default=False)),
                ('gdpr_issues', models.JSONField(blank=True, default=list)),
                ('gdpr_compliance_summary', models.TextField(blank=True, default='')),
                ('recommendations', models.JSONField(blank=True, default=list, help_text='Ordered list of security recommendations')),
                ('analysis_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('analysis_version', models.CharField(default='1.0.0', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('document', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='security_analysis',
                    to='api.document',
                )),
            ],
            options={
                'verbose_name': 'Document Security Analysis',
                'verbose_name_plural': 'Document Security Analyses',
                'ordering': ['-analysis_date'],
            },
        ),
        migrations.AddIndex(
            model_name='documentsecurityanalysis',
            index=models.Index(fields=['risk_level', '-analysis_date'], name='security_do_risk_le_idx'),
        ),
        migrations.AddIndex(
            model_name='documentsecurityanalysis',
            index=models.Index(fields=['confidentiality_level', '-analysis_date'], name='security_do_conf_le_idx'),
        ),
        migrations.AddIndex(
            model_name='documentsecurityanalysis',
            index=models.Index(fields=['gdpr_status', '-analysis_date'], name='security_do_gdpr_st_idx'),
        ),
    ]
