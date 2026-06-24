"""
Migration 0015 — Add missing fields to TrainingJob and MLOpsConfig.

TrainingJob:
  - accuracy          FloatField (best model accuracy on test set)
  - duration_seconds  FloatField (auto-computed on save)
  - dataset_size      PositiveIntegerField (alias for documents_count)

MLOpsConfig:
  - training_count    PositiveIntegerField (total completed training runs)
  - dataset_size      PositiveIntegerField (samples at last training run)
  - last_model_version CharField (backwards-compat alias for current_model_version)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0014_trainingjob_log_output'),
    ]

    operations = [
        # ── TrainingJob ───────────────────────────────────────────────────────
        migrations.AddField(
            model_name='trainingjob',
            name='accuracy',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='trainingjob',
            name='duration_seconds',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='trainingjob',
            name='dataset_size',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Number of samples used in this training run (alias for documents_count)',
            ),
        ),
        # ── MLOpsConfig ───────────────────────────────────────────────────────
        migrations.AddField(
            model_name='mlopsconfig',
            name='training_count',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Total number of completed training runs',
            ),
        ),
        migrations.AddField(
            model_name='mlopsconfig',
            name='dataset_size',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Number of samples at last training run',
            ),
        ),
        migrations.AddField(
            model_name='mlopsconfig',
            name='last_model_version',
            field=models.CharField(
                blank=True,
                default='',
                max_length=100,
                help_text='Alias kept for backwards compatibility',
            ),
        ),
    ]
