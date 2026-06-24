# ci/check_dataset.py — Stage 4: verifie le volume minimum de samples labellises
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from api.models import RuleTrainingSample

total = RuleTrainingSample.objects.filter(label__in=['approved', 'rejected']).count()
print('[INFO] Labeled RuleTrainingSamples:', total)

if total < 20:
    print('[FAIL] Insufficient samples (< 20) - pipeline aborted.')
    sys.exit(1)

print('[OK] Dataset valid:', total, 'labeled samples')
