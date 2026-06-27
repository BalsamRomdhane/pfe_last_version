# Data migration — fixes existing MLOpsConfig and TrainingJob records:
#
# 1. MLOpsConfig rows with retraining_threshold=1 (old default) are updated
#    to 10 (the value from MLOPS_RETRAINING_THRESHOLD env var / new default).
#
# 2. TrainingJob rows whose model_version starts with "jenkins-0-" (produced
#    by local runs before the fix) are cleaned to just the algorithm name.
#
# 3. MLOpsConfig rows whose current_model_version starts with "jenkins-0-"
#    are cleaned the same way.

from django.db import migrations


def fix_threshold_and_model_versions(apps, schema_editor):
    MLOpsConfig = apps.get_model('api', 'MLOpsConfig')
    TrainingJob = apps.get_model('api', 'TrainingJob')

    # Fix threshold: any row still at the old default of 1 → 10
    MLOpsConfig.objects.filter(retraining_threshold=1).update(retraining_threshold=10)

    # Clean model_version on TrainingJob rows
    for job in TrainingJob.objects.filter(model_version__startswith='jenkins-0-'):
        job.model_version = job.model_version[len('jenkins-0-'):]
        job.save(update_fields=['model_version'])

    # Clean current_model_version on MLOpsConfig rows
    for cfg in MLOpsConfig.objects.filter(current_model_version__startswith='jenkins-0-'):
        cfg.current_model_version = cfg.current_model_version[len('jenkins-0-'):]
        cfg.save(update_fields=['current_model_version'])


def reverse_fix(apps, schema_editor):
    # Non-reversible: we don't restore placeholder values
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0016_fix_mlopsconfig_threshold_default'),
    ]

    operations = [
        migrations.RunPython(fix_threshold_and_model_versions, reverse_code=reverse_fix),
    ]
