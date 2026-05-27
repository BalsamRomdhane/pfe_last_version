from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0008_ruletrainingsample_alter_document_status_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='trainingsample',
            name='valid_rules_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='trainingsample',
            name='invalid_rules_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='trainingsample',
            name='total_rules',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='trainingsample',
            name='rule_results_json',
            field=models.JSONField(default=list, blank=True),
        ),
        migrations.AddField(
            model_name='trainingsample',
            name='compliance_score',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='trainingsample',
            name='approved_rules',
            field=models.JSONField(default=list, blank=True),
        ),
        migrations.AddField(
            model_name='trainingsample',
            name='rejected_rules',
            field=models.JSONField(default=list, blank=True),
        ),
    ]
