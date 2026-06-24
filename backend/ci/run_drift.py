# ci/run_drift.py — Stage 5: calcule le drift score pour toutes les normes
import os
import sys
import json

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from services.mlops_service import compute_drift_score
from api.models import Norme

# artifacts/ est deux niveaux au-dessus de ci/ (workspace/artifacts)
artifacts_dir = os.path.join(_BACKEND, '..', 'artifacts')
os.makedirs(artifacts_dir, exist_ok=True)

results = {}
for norm in Norme.objects.all():
    result = compute_drift_score(norm.name)
    score  = result.get('drift_score', 0.0)
    status = result.get('status', 'unknown')
    print('[DRIFT] %-45s score=%.4f  status=%s' % (norm.name[:45], score, status))
    results[norm.name] = result

out = os.path.join(artifacts_dir, 'drift_report.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, default=str)

print('[OK] Drift report saved ->', out)
