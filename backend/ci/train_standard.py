# ci/train_standard.py — Stage 6: entraine les modeles ML pour une norme donnee
# Usage: python ci/train_standard.py ISO9001
#        python ci/train_standard.py ISO27001
#        python ci/train_standard.py TISAX
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from ml.train_models import train_all_models
from api.models import Norme

target = sys.argv[1] if len(sys.argv) > 1 else 'ISO9001'

if target.upper() == 'ISO9001':
    result = train_all_models(standard=None, dataset_type='classification')
    standard_name = 'ISO9001'
else:
    keyword = '27001' if '27001' in target.upper() else 'tisax'
    norm = Norme.objects.filter(name__icontains=keyword).first()
    if not norm:
        print('[WARN] Norm not found for keyword "%s" - skipping.' % keyword)
        sys.exit(0)
    result = train_all_models(standard=norm.name, dataset_type='classification')
    standard_name = norm.name

if isinstance(result, dict) and 'error' in result:
    print('[WARN] Training skipped:', result['error'])
    sys.exit(0)

# ── Update MLOpsConfig after a successful local training run ──────────────────
# training_count is incremented here so that local (non-Jenkins) runs are
# reflected in the MLOps dashboard alongside Jenkins-triggered runs.
try:
    from django.utils import timezone as _tz
    from django.db.models import F as _F
    from api.models import MLOpsConfig

    best_trained = [
        v for v in (result.get('results') or {}).values()
        if not v.get('error') and v.get('f1_score')
    ]
    best_f1 = max((v.get('f1_score', 0) for v in best_trained), default=0.0)

    MLOpsConfig.objects.filter(standard__iexact=standard_name).update(
        last_trained_at=_tz.now(),
        last_trained_doc_count=result.get('samples', 0),
        dataset_size=result.get('samples', 0),
        last_f1_score=best_f1,
        current_model_version='local-' + _tz.now().strftime('%Y%m%d-%H%M%S'),
        training_count=_F('training_count') + 1,
    )
    print('[OK] MLOpsConfig updated for standard=%s' % standard_name)
except Exception as _exc:
    print('[WARN] Could not update MLOpsConfig: %s' % _exc)

print('[OK] %-10s best=%-20s samples=%d' % (
    target,
    result.get('best_model', '?'),
    result.get('samples', 0)
))
