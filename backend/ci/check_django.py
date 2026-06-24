# ci/check_django.py — Stage 3: verifie que Django et les modeles MLOps sont operationnels
import os
import sys

# Assure que le dossier backend/ est dans le path (pour enterprise_platform)
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from api.models import Norme, RuleTrainingSample, TrainingJob

fields = [f.name for f in TrainingJob._meta.get_fields()]
if 'log_output' not in fields:
    print('[FAIL] TrainingJob.log_output absent - relancer: manage.py migrate')
    sys.exit(1)

print('[OK] Django OK')
print('[OK] Norme:', Norme.objects.count())
print('[OK] RuleTrainingSample:', RuleTrainingSample.objects.count())
print('[OK] TrainingJob.log_output confirmed')
