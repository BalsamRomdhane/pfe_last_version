# ci/export_metrics.py — Stage 7: exporte les metriques Prometheus et l'evaluation summary
import os
import sys
import json
import glob

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from services.mlops_service import get_prometheus_metrics

artifacts_dir = os.path.join(_BACKEND, '..', 'artifacts')
os.makedirs(artifacts_dir, exist_ok=True)

# -- Prometheus metrics
prom = get_prometheus_metrics()
prom_out = os.path.join(artifacts_dir, 'prometheus_metrics.txt')
with open(prom_out, 'w', encoding='utf-8') as f:
    f.write(prom)
print('[OK] Prometheus metrics ->', prom_out)

# -- Evaluation summary from *_metrics.json
models_dir = os.path.join(_BACKEND, 'ml', 'models')
summary = []

for mf in sorted(glob.glob(os.path.join(models_dir, '*_metrics.json'))):
    with open(mf, 'r', encoding='utf-8') as f:
        data = json.load(f)
    norm_key = os.path.basename(mf).replace('_metrics.json', '')
    best     = data.get('best_model', '?')
    samples  = data.get('samples', 0)
    print('')
    print('[EVAL] %s' % norm_key)
    print('       Best model : %s  |  Samples : %d' % (best, samples))
    for m, v in data.get('results', {}).items():
        # FIX: guard against None values when a model failed to save
        f1   = v.get('f1_score')   or 0.0
        acc  = v.get('accuracy')   or 0.0
        prec = v.get('precision')  or 0.0
        rec  = v.get('recall')     or 0.0
        print('       %-22s  f1=%.4f  acc=%.4f  prec=%.4f  rec=%.4f' % (
            m, f1, acc, prec, rec,
        ))
    summary.append({'norm': norm_key, 'best_model': best, 'samples': samples})

eval_out = os.path.join(artifacts_dir, 'evaluation_summary.json')
with open(eval_out, 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print('')
print('[OK] Evaluation summary ->', eval_out)
