"""
fix_mlops_data.py
-----------------
Supprime les entrées MLOpsConfig et TrainingJob qui ne correspondent
à aucune norme réelle dans la base de données :
  - standard='default'   (produit quand aucun standard n'est fourni)
  - standard='unknown'   (produit quand la norme n'est pas résolue)
  - standard='ISO9001'   (alias court jamais utilisé par le pipeline réel)

Ces entrées sont des artefacts de développement et polluent le dashboard.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from api.models import MLOpsConfig, TrainingJob, Norme
from django.db.models import Count

# Collect real norm names
real_norms = set(Norme.objects.values_list('name', flat=True))
print('Real norms in DB:', real_norms)

# Orphan standards = not in real_norms
all_cfg_standards = set(MLOpsConfig.objects.values_list('standard', flat=True))
orphan_standards  = all_cfg_standards - real_norms
print('Orphan standards to remove:', orphan_standards)

if orphan_standards:
    cfg_del = MLOpsConfig.objects.filter(standard__in=orphan_standards).delete()
    job_del = TrainingJob.objects.filter(standard__in=orphan_standards).delete()
    print('Deleted MLOpsConfig:', cfg_del)
    print('Deleted TrainingJob:', job_del)
else:
    print('No orphan standards found — nothing to delete.')

print()
print('=== Remaining MLOpsConfig ===')
for c in MLOpsConfig.objects.all():
    print(f'  standard={c.standard!r}')
    print(f'    threshold={c.retraining_threshold}  f1={c.last_f1_score}  version={c.current_model_version!r}')

print()
print('=== TrainingJob counts by standard ===')
for row in TrainingJob.objects.values('standard').annotate(n=Count('id')).order_by('standard'):
    print(f'  {row["standard"]!r}  count={row["n"]}')
