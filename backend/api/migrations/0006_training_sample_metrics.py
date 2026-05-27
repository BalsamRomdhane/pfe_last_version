from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_rule_severity_condition_action'),
    ]

    operations = [
        migrations.AddField(
            model_name='trainingsample',
            name='norm_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='trainingsample',
            name='confidence_score',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='trainingsample',
            name='teamlead_decision',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='trainingsample',
            name='approved',
            field=models.BooleanField(null=True),
        ),
    ]
