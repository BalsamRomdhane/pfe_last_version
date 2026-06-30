"""
normalize_model_versions.py
----------------------------
Normalise tous les model_version dans TrainingJob et MLOpsConfig
qui utilisent l'ancien format "jenkins-{N}-{Algo}" vers "{Algo} v{N}".

Exemples :
  "jenkins-13-BiLSTM"    → "BiLSTM v13"
  "jenkins-0-BiLSTM"     → "BiLSTM"          (pas de numéro de build)
  "BiLSTM"               → inchangé
  "RandomForest"         → inchangé
  "jenkins-42-RandomForest" → "RandomForest v42"
"""

import os
import sys
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from api.models import TrainingJob, MLOpsConfig

PATTERN = re.compile(r'^jenkins-(\d+)-(.+)$')


def normalize(raw):
    if not raw:
        return raw
    m = PATTERN.match(raw)
    if not m:
        return raw  # already clean
    build_num = m.group(1)
    algo      = m.group(2)
    if build_num == '0':
        return algo          # local run: no build number
    return f'{algo} v{build_num}'


# Fix TrainingJob
changed_jobs = 0
for job in TrainingJob.objects.all():
    clean = normalize(job.model_version)
    if clean != job.model_version:
        print(f'  TrainingJob #{job.id} [{job.standard}]: {job.model_version!r} -> {clean!r}')
        job.model_version = clean
        job.save(update_fields=['model_version'])
        changed_jobs += 1

# Fix MLOpsConfig
changed_cfg = 0
for cfg in MLOpsConfig.objects.all():
    clean = normalize(cfg.current_model_version)
    if clean != cfg.current_model_version:
        print(f'  MLOpsConfig [{cfg.standard}]: {cfg.current_model_version!r} -> {clean!r}')
        cfg.current_model_version = clean
        cfg.save(update_fields=['current_model_version'])
        changed_cfg += 1

print(f'\nDone. Updated {changed_jobs} TrainingJob(s), {changed_cfg} MLOpsConfig(s).')

print('\n=== Final state ===')
for c in MLOpsConfig.objects.all().order_by('standard'):
    print(f'  [{c.standard}]  version={c.current_model_version!r}  f1={c.last_f1_score}  threshold={c.retraining_threshold}')
