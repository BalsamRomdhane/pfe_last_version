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
else:
    keyword = '27001' if '27001' in target.upper() else 'tisax'
    norm = Norme.objects.filter(name__icontains=keyword).first()
    if not norm:
        print('[WARN] Norm not found for keyword "%s" - skipping.' % keyword)
        sys.exit(0)
    result = train_all_models(standard=norm.name, dataset_type='classification')

if isinstance(result, dict) and 'error' in result:
    print('[WARN] Training skipped:', result['error'])
    sys.exit(0)

print('[OK] %-10s best=%-20s samples=%d' % (
    target,
    result.get('best_model', '?'),
    result.get('samples', 0)
))
