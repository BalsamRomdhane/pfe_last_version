# Generated migration to add fields to TrainingSample

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_alter_trainingsample_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='trainingsample',
            name='rule_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='trainingsample',
            name='rule_text',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='trainingsample',
            name='document_text',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='trainingsample',
            name='evidence_text',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='trainingsample',
            name='semantic_score',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='trainingsample',
            name='feature_vector',
            field=models.JSONField(default=dict),
        ),
    ]
