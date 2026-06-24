# Migration manuelle : ajoute le champ log_output à TrainingJob
# Requis car mlops_service.py écrit job.log_output mais le champ
# n'existe pas dans la migration d'origine (0011_mlopsconfig_trainingjob.py)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0013_rename_api_document_standard_4f81a0_idx_api_documen_standar_63ca70_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='trainingjob',
            name='log_output',
            field=models.TextField(blank=True, default=''),
        ),
    ]
