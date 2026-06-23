from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0011_mlopsconfig_trainingjob'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentTrainingSample',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('standard', models.CharField(default='ISO9001', max_length=50)),
                ('total_rules', models.PositiveIntegerField(default=0)),
                ('passed_rules', models.PositiveIntegerField(default=0)),
                ('failed_rules', models.PositiveIntegerField(default=0)),
                ('compliance_score', models.FloatField(default=0.0)),
                ('critical_rules_passed', models.PositiveIntegerField(default=0)),
                ('high_rules_passed', models.PositiveIntegerField(default=0)),
                ('medium_rules_passed', models.PositiveIntegerField(default=0)),
                ('low_rules_passed', models.PositiveIntegerField(default=0)),
                ('evidence_count', models.PositiveIntegerField(default=0)),
                ('text_length', models.PositiveIntegerField(default=0)),
                ('paragraph_count', models.PositiveIntegerField(default=0)),
                ('feature_vector', models.JSONField(blank=True, default=list)),
                ('label', models.CharField(blank=True, default='pending', max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('document', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='document_training_sample', to='api.document')),
            ],
            options={
                'ordering': ['-created_at'],
                'verbose_name': 'Document Training Sample',
                'verbose_name_plural': 'Document Training Samples',
            },
        ),
        migrations.AddIndex(
            model_name='documenttrainingsample',
            index=models.Index(fields=['standard', '-created_at'], name='api_document_standard_4f81a0_idx'),
        ),
        migrations.AddIndex(
            model_name='documenttrainingsample',
            index=models.Index(fields=['label', '-created_at'], name='api_document_label_7b1d9c_idx'),
        ),
    ]
