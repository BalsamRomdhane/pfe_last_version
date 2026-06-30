"""
ci/resync_mlops_from_json.py
Resynchronise MLOpsConfig et crée des TrainingJob corrects
depuis les *_metrics.json produits par le dernier entraînement.

Corrections appliquées :
  - accuracy stockée dans TrainingJob.accuracy (et avg_similarity pour compat)
  - model_version = nom de l'algorithme (sans préfixe jenkins-0-)
  - dataset_size mis à jour
  - training_count réinitialisé à 1 (ce run)
  - f1, precision, recall depuis le vrai best model du JSON
"""
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

from api.models import TrainingJob, MLOpsConfig, Norme
from django.utils import timezone

models_dir = os.path.join(_BACKEND, 'ml', 'models')
metrics_files = sorted(glob.glob(os.path.join(models_dir, '*_metrics.json')))
metrics_files = [f for f in metrics_files if 'evidence' not in os.path.basename(f).lower()]

print('[resync] Scanning %d metrics files...' % len(metrics_files))
synced = 0

for mf in metrics_files:
    with open(mf, 'r', encoding='utf-8') as fh:
        data = json.load(fh)

    standard = data.get('standard', '')
    if not standard:
        print('[SKIP] %s — standard=null' % os.path.basename(mf))
        continue

    # Verify norm exists in DB
    norm = Norme.objects.filter(name__iexact=standard).first()
    if not norm:
        print('[SKIP] %s — norm not found for standard=%s' % (os.path.basename(mf), standard))
        continue

    best_model = data.get('best_model', '')
    samples = int(data.get('dataset_size') or data.get('samples') or 0)
    bm = data.get('results', {}).get(best_model, {})
    trained_at_str = data.get('trained_at')

    f1        = float(bm.get('f1_score', 0.0) or 0.0)
    precision = float(bm.get('precision', 0.0) or 0.0)
    recall    = float(bm.get('recall', 0.0) or 0.0)
    accuracy  = float(bm.get('accuracy', 0.0) or 0.0)

    # Parse trained_at
    try:
        from datetime import datetime
        trained_dt = datetime.strptime(trained_at_str, '%Y-%m-%d %H:%M:%S') if trained_at_str else None
        from django.utils import timezone as tz
        from datetime import timezone as _utc
        if trained_dt:
            trained_dt = trained_dt.replace(tzinfo=_utc.utc)
        else:
            trained_dt = tz.now()
    except Exception:
        from django.utils import timezone as tz
        trained_dt = tz.now()

    # Create a fresh corrected TrainingJob
    job = TrainingJob.objects.create(
        standard=norm.name,
        status='success',
        start_time=trained_dt,
        end_time=trained_dt,
        documents_count=samples,
        dataset_size=samples,
        new_docs_since=0,
        f1_score=f1,
        precision_score=precision,
        recall_score=recall,
        accuracy=accuracy,           # FIX #8: correct field
        avg_similarity=accuracy,     # backward compat alias
        model_version=best_model,    # clean version (no jenkins-0- prefix)
        triggered_by='resync',
        drift_report={},
        log_output='[resync] from %s | best=%s | f1=%.4f | acc=%.4f' % (
            os.path.basename(mf), best_model, f1, accuracy),
    )

    # Update MLOpsConfig — authoritative values
    cfg, created = MLOpsConfig.objects.get_or_create(
        standard=norm.name,
        defaults={'retraining_threshold': 10},
    )
    MLOpsConfig.objects.filter(standard=norm.name).update(
        last_trained_at=trained_dt,
        last_trained_doc_count=samples,
        current_model_version=best_model,
        last_f1_score=f1,
        dataset_size=samples,
        training_count=1,
    )

    print('[OK] %-55s best=%-20s f1=%.4f acc=%.4f samples=%d job_id=%d' % (
        norm.name, best_model, f1, accuracy, samples, job.id))
    synced += 1

print()
print('[resync] %d MLOpsConfig entries updated.' % synced)
print()

# Verify final state
print('=== Final DB State ===')
for cfg in MLOpsConfig.objects.exclude(standard='default').order_by('standard'):
    print('  [%s]' % cfg.standard)
    print('    f1=%.4f  version=%s  training_count=%d  dataset_size=%d' % (
        cfg.last_f1_score or 0, cfg.current_model_version or 'None',
        cfg.training_count, cfg.dataset_size))

# Check latest jobs
print()
print('=== Latest TrainingJobs ===')
for j in TrainingJob.objects.exclude(standard='default').order_by('-created_at')[:6]:
    print('  #%d [%s] f1=%.4f acc=%.4f version=%s triggered=%s' % (
        j.id, j.standard, j.f1_score or 0, j.accuracy or 0,
        j.model_version, j.triggered_by))
