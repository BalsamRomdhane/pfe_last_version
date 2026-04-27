from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_training_sample'),
    ]

    operations = [
        migrations.AddField(
            model_name='trainingsample',
            name='standard',
            field=models.CharField(default='ISO9001', max_length=50),
        ),
        migrations.AddIndex(
            model_name='trainingsample',
            index=models.Index(fields=['standard', '-created_at'], name='api_training_standard_idx'),
        ),
    ]
