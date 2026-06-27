"""
ci/update_training_job.py - Stage 8
Enregistre les TrainingJob et met a jour MLOpsConfig depuis les *_metrics.json
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

build_id = os.getenv('BUILD_NUMBER', '0')
build_url = os.getenv('BUILD_URL', '')
created = 0

models_dir = os.path.join(_BACKEND, 'ml', 'models')
metrics_files = sorted(glob.glob(os.path.join(models_dir, '*_metrics.json')))

# Skip FAISS/evidence index files
metrics_files = [f for f in metrics_files
                 if 'evidence' not in os.path.basename(f).lower()]

if not metrics_files:
    print('[WARN] No *_metrics.json found - training may have been skipped or failed.')
    sys.exit(0)

def _find_norm_from_filename(filename):
    """
    Infer the real Norme from the metrics filename.
    Filenames look like:
      ISO_9001___Controle_et_validation_des_documents_metrics.json
      ISO_27001___Securite_de_l_information_metrics.json
      TISAX___Information_Security_Assessment_metrics.json
    """
    basename = os.path.basename(filename).replace('_metrics.json', '')
    # Try exact match first using the norm name reconstructed from filename
    # Strategy: check each DB norm by keyword
    for kw, norm_qs in [
        ('9001',  Norme.objects.filter(name__icontains='9001')),
        ('27001', Norme.objects.filter(name__icontains='27001')),
        ('tisax', Norme.objects.filter(name__icontains='tisax')),
    ]:
        if kw in basename.lower().replace('_', '').replace('-', ''):
            norm = norm_qs.first()
            if norm:
                return norm
    return None

for mf in metrics_files:
    with open(mf, 'r', encoding='utf-8') as fh:
        data = json.load(fh)

    best_model = data.get('best_model', '')
    # dataset_size is the correct field in newer metrics (samples may be 0)
    samples = int(data.get('dataset_size', data.get('samples', 0)))
    bm = data.get('results', {}).get(best_model, {})

    # Resolve norm: try field in JSON, then infer from filename
    standard_from_file = data.get('standard', '')
    norm = None
    if standard_from_file:
        norm = Norme.objects.filter(name__iexact=standard_from_file).first()
        if not norm:
            for kw in ['9001', '27001', 'tisax']:
                if kw in standard_from_file.lower():
                    norm = Norme.objects.filter(name__icontains=kw).first()
                    break
    if not norm:
        norm = _find_norm_from_filename(mf)

    standard_key = norm.name if norm else os.path.basename(mf).replace('_metrics.json', '')

    # Build a clean model_version string:
    # - With real Jenkins: "RandomForest v42" (BUILD_NUMBER=42)
    # - Without Jenkins (local): "RandomForest" (no build number prefix)
    if build_id and build_id != '0':
        model_version_str = '%s v%s' % (best_model, build_id)
    else:
        model_version_str = best_model  # local training: just the algorithm name

    job = TrainingJob.objects.create(
        standard=standard_key,
        status='success',
        start_time=timezone.now(),
        end_time=timezone.now(),
        documents_count=samples,
        new_docs_since=0,
        f1_score=float(bm.get('f1_score', 0.0)),
        precision_score=float(bm.get('precision', 0.0)),
        recall_score=float(bm.get('recall', 0.0)),
        avg_similarity=float(bm.get('accuracy', 0.0)),
        model_version=model_version_str,
        jenkins_build_id=build_id if build_id != '0' else '',
        jenkins_url=build_url,
        triggered_by='jenkins' if build_id != '0' else 'local',
        drift_report=data.get('dataset_quality', {}),
        log_output='Build #%s | %s | best=%s' % (build_id, standard_key, best_model),
    )

    MLOpsConfig.objects.update_or_create(
        standard=standard_key,
        defaults={
            'last_trained_at': timezone.now(),
            'last_trained_doc_count': samples,
            'current_model_version': model_version_str,
            'last_f1_score': float(bm.get('f1_score', 0.0)),
        }
    )
    print('[OK] TrainingJob #%d | %-55s f1=%.4f' % (
        job.id, standard_key, float(bm.get('f1_score', 0))
    ))
    created += 1

print('[OK] %d TrainingJob(s) recorded in database.' % created)
