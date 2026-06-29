"""
MLOps Service — manages training job lifecycle, document counting,
drift detection, and Jenkins pipeline triggers.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests
from django.conf import settings
from django.utils import timezone as tz

logger = logging.getLogger(__name__)

# ── Jenkins config from env ───────────────────────────────────────────────────
# NOTE: These module-level constants are kept for backward compatibility with
# trigger_jenkins_pipeline(). All health-check functions re-read from os.getenv()
# at call time so .env changes are picked up after a Daphne restart.
_JENKINS_URL_DEFAULT      = 'http://localhost:8089'
_JENKINS_USER_DEFAULT     = 'jenkins_admin'
_JENKINS_TOKEN_DEFAULT    = ''
_JENKINS_JOB_DEFAULT      = 'compliance-ml-pipeline'
RETRAINING_THRESHOLD      = int(os.getenv('MLOPS_RETRAINING_THRESHOLD', '10'))


def _jenkins_cfg():
    """Return current Jenkins config from environment (re-read on every call)."""
    return {
        'url':   os.getenv('JENKINS_URL',      _JENKINS_URL_DEFAULT).rstrip('/'),
        'user':  os.getenv('JENKINS_USER',     _JENKINS_USER_DEFAULT),
        'token': os.getenv('JENKINS_TOKEN',    _JENKINS_TOKEN_DEFAULT),
        'job':   os.getenv('JENKINS_JOB_NAME', _JENKINS_JOB_DEFAULT),
    }


# Backward-compat aliases used by trigger_jenkins_pipeline()
def _get_jenkins_url():   return _jenkins_cfg()['url']
def _get_jenkins_user():  return _jenkins_cfg()['user']
def _get_jenkins_token(): return _jenkins_cfg()['token']
def _get_jenkins_job():   return _jenkins_cfg()['job']


# ── Jenkins Health Service ────────────────────────────────────────────────────
def get_jenkins_health() -> Dict[str, Any]:
    """
    Perform a real health check against Jenkins.

    Returns a structured status object with five distinct states:

    1. not_configured  — JENKINS_TOKEN is empty → local training only
    2. unreachable     — token set but Jenkins host doesn't respond
    3. auth_failed     — Jenkins responds but credentials are wrong (401/403)
    4. job_not_found   — authenticated but the configured job doesn't exist
    5. connected       — fully operational, remote trigger available

    The 'local_training' flag is always True: the ML pipeline can run
    locally regardless of Jenkins availability.
    """
    cfg    = _jenkins_cfg()
    _url   = cfg['url']
    _user  = cfg['user']
    _token = cfg['token']
    _job   = cfg['job']

    base = {
        'local_training': True,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'jenkins_url': _url if _token else None,
        'job_name':    _job if _token else None,
    }

    # ── Case 1: token not set ─────────────────────────────────────────────
    if not _token.strip():
        return {
            **base,
            'configured':    False,
            'reachable':     False,
            'authenticated': False,
            'connected':     False,
            'remote_trigger': False,
            'version':       None,
            'status':        'not_configured',
            'message': (
                'Remote Jenkins API is not configured. '
                'Set JENKINS_TOKEN in backend/.env and restart the server. '
                'Local model training remains available.'
            ),
        }

    # ── Case 2: reachability check ────────────────────────────────────────
    try:
        resp = requests.get(
            f'{_url}/api/json',
            auth=(_user, _token),
            timeout=5,
            headers={'Accept': 'application/json'},
        )
    except requests.exceptions.ConnectionError:
        return {
            **base,
            'configured':    True,
            'reachable':     False,
            'authenticated': False,
            'connected':     False,
            'remote_trigger': False,
            'version':       None,
            'status':        'unreachable',
            'message':       f'Unable to reach Jenkins at {_url}. Check server status or network.',
        }
    except requests.exceptions.Timeout:
        return {
            **base,
            'configured':    True,
            'reachable':     False,
            'authenticated': False,
            'connected':     False,
            'remote_trigger': False,
            'version':       None,
            'status':        'unreachable',
            'message':       f'Jenkins at {_url} did not respond within 5 seconds.',
        }
    except Exception as exc:
        return {
            **base,
            'configured':    True,
            'reachable':     False,
            'authenticated': False,
            'connected':     False,
            'remote_trigger': False,
            'version':       None,
            'status':        'error',
            'message':       f'Jenkins check failed: {exc}',
        }

    # ── Case 3: authentication check ─────────────────────────────────────
    if resp.status_code in (401, 403):
        return {
            **base,
            'configured':    True,
            'reachable':     True,
            'authenticated': False,
            'connected':     False,
            'remote_trigger': False,
            'version':       None,
            'status':        'auth_failed',
            'message': (
                f'Jenkins responded but rejected credentials for user "{_user}". '
                'Verify JENKINS_USER and JENKINS_TOKEN in backend/.env.'
            ),
        }

    version = resp.headers.get('X-Jenkins', None)

    # ── Case 4: job existence check ───────────────────────────────────────
    try:
        job_resp = requests.get(
            f'{_url}/job/{_job}/api/json',
            auth=(_user, _token),
            timeout=5,
            headers={'Accept': 'application/json'},
        )
        job_exists = job_resp.status_code == 200
    except Exception:
        job_exists = False

    if not job_exists:
        return {
            **base,
            'configured':    True,
            'reachable':     True,
            'authenticated': True,
            'connected':     False,
            'remote_trigger': False,
            'version':       version,
            'status':        'job_not_found',
            'message': (
                f'Connected to Jenkins v{version or "?"} at {_url}, '
                f'but pipeline job "{_job}" was not found. '
                'Check JENKINS_JOB_NAME in backend/.env.'
            ),
        }

    # ── Case 5: fully connected ───────────────────────────────────────────
    return {
        **base,
        'configured':    True,
        'reachable':     True,
        'authenticated': True,
        'connected':     True,
        'remote_trigger': True,
        'version':       version,
        'status':        'connected',
        'message':       f'Jenkins connected — {_url} — job: {_job} — v{version or "?"}',
    }


# ── Document/sample counting ─────────────────────────────────────────────────
def get_jenkins_builds(limit: int = 10) -> Dict[str, Any]:
    """Fetch recent builds from Jenkins for the configured job."""
    cfg = _jenkins_cfg()
    _url, _user, _token, _job = cfg['url'], cfg['user'], cfg['token'], cfg['job']

    if not _token:
        return {'builds': [], 'error': 'Jenkins not configured'}

    try:
        resp = requests.get(
            f'{_url}/job/{_job}/api/json'
            f'?tree=builds[number,status,result,timestamp,duration,url,displayName]{{,{limit}}}',
            auth=(_user, _token),
            timeout=10,
            headers={'Accept': 'application/json'},
        )
        if resp.status_code == 200:
            data = resp.json()
            return {'builds': data.get('builds', []), 'job': _job, 'url': _url}
        return {'builds': [], 'error': f'HTTP {resp.status_code}'}
    except Exception as exc:
        return {'builds': [], 'error': str(exc)}


def get_jenkins_last_build() -> Dict[str, Any]:
    """Fetch the last build info from Jenkins."""
    cfg = _jenkins_cfg()
    _url, _user, _token, _job = cfg['url'], cfg['user'], cfg['token'], cfg['job']

    if not _token:
        return {'error': 'Jenkins not configured'}

    try:
        resp = requests.get(
            f'{_url}/job/{_job}/lastBuild/api/json',
            auth=(_user, _token),
            timeout=10,
            headers={'Accept': 'application/json'},
        )
        if resp.status_code == 200:
            return resp.json()
        return {'error': f'HTTP {resp.status_code}'}
    except Exception as exc:
        return {'error': str(exc)}


# ── Document/sample counting ─────────────────────────────────────────────────
def count_new_documents(standard: str) -> Dict[str, Any]:
    """Return count of labeled RuleTrainingSamples added since last training.

    This is the authoritative "new docs" metric because the ML pipeline trains
    on RuleTrainingSample rows, not on raw Document uploads.
    The legacy 'total_documents' field is kept for backward compatibility.
    """
    from api.models import RuleTrainingSample, MLOpsConfig

    config, _ = MLOpsConfig.objects.get_or_create(
        standard=standard,
        defaults={'retraining_threshold': RETRAINING_THRESHOLD},
    )

    qs_labeled = RuleTrainingSample.objects.filter(
        norm__name__iexact=standard,
        label__in=['approved', 'rejected'],
    )
    total = qs_labeled.count()

    if config.last_trained_at:
        new_docs = qs_labeled.filter(created_at__gt=config.last_trained_at).count()
    else:
        new_docs = total

    needs_training = (
        config.auto_trigger_enabled
        and new_docs >= config.retraining_threshold
    )

    return {
        'standard': standard,
        'total_documents': total,       # labeled RuleTrainingSamples — pipeline training source
        'new_documents': new_docs,
        'last_trained_at': config.last_trained_at.isoformat() if config.last_trained_at else None,
        'threshold': config.retraining_threshold,
        'needs_training': needs_training,
        'current_model_version': config.current_model_version or None,
    }


# ── Drift analysis ────────────────────────────────────────────────────────────
def compute_drift_score(standard: str) -> Dict[str, Any]:
    """
    Compare embeddings of recent vs historical RuleTrainingSamples.
    Returns drift score (0=stable, 1=max drift) and report.
    """
    from api.models import RuleTrainingSample, MLOpsConfig

    config, _ = MLOpsConfig.objects.get_or_create(standard=standard)

    qs = RuleTrainingSample.objects.filter(
        norm__name__iexact=standard
    ).order_by('created_at')

    total = qs.count()
    if total < 6:
        return {
            'drift_score': 0.0,
            'total_samples': total,
            'historical_count': 0,
            'recent_count': 0,
            'status': 'insufficient_data',
            'message': f'Only {total} samples — need at least 6 to compute drift.',
        }

    # Split 70% historical / 30% recent
    split = int(total * 0.7)
    historical = list(qs[:split].values_list('evidence_text', flat=True))
    recent     = list(qs[split:].values_list('evidence_text', flat=True))

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity as cos_sim

        texts = [t or '' for t in historical + recent]
        vect = TfidfVectorizer(max_features=512, stop_words='english')
        mat = vect.fit_transform(texts).toarray()

        hist_mat   = mat[:len(historical)]
        recent_mat = mat[len(historical):]

        hist_mean   = hist_mat.mean(axis=0)
        recent_mean = recent_mat.mean(axis=0)

        similarity  = float(cos_sim([hist_mean], [recent_mean])[0][0])
        drift_score = round(1.0 - similarity, 4)

        hist_labels   = list(qs[:split].values_list('label', flat=True))
        recent_labels = list(qs[split:].values_list('label', flat=True))

        def label_dist(labels):
            total_ = max(len(labels), 1)
            approved = labels.count('approved')
            rejected = labels.count('rejected')
            return {
                'approved_pct': round(approved / total_ * 100, 1),
                'rejected_pct': round(rejected / total_ * 100, 1),
            }

        return {
            'drift_score': drift_score,
            'total_samples': total,
            'historical_count': len(historical),
            'recent_count': len(recent),
            'cosine_similarity': similarity,
            'historical_distribution': label_dist(hist_labels),
            'recent_distribution': label_dist(recent_labels),
            'status': 'critical' if drift_score > 0.3 else ('warning' if drift_score > 0.15 else 'stable'),
            'computed_at': datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.exception('Drift computation failed')
        return {
            'drift_score': 0.0,
            'status': 'error',
            'message': str(e),
        }


# ── Jenkins trigger ───────────────────────────────────────────────────────────
def trigger_jenkins_pipeline(standard: str, doc_info: Dict[str, Any]) -> Dict[str, Any]:
    """POST to Jenkins to trigger the ML pipeline job."""
    from api.models import TrainingJob, MLOpsConfig

    cfg = _jenkins_cfg()
    _url   = cfg['url']
    _user  = cfg['user']
    _token = cfg['token']
    _job   = cfg['job']

    if not _token:
        logger.warning('JENKINS_TOKEN not configured — skipping Jenkins trigger.')
        return {'triggered': False, 'reason': 'JENKINS_TOKEN not configured in backend/.env'}

    job = TrainingJob.objects.create(
        status='pending',
        standard=standard,
        documents_count=doc_info.get('total_documents', 0),
        new_docs_since=doc_info.get('new_documents', 0),
        triggered_by='auto',
    )

    params = {
        'STANDARD':        standard,
        'DOCUMENT_COUNT':  str(doc_info.get('total_documents', 0)),
        'NEW_DOCS':        str(doc_info.get('new_documents', 0)),
        'JOB_ID':          str(job.id),
        'API_URL':         os.getenv('DJANGO_API_URL', 'http://localhost:8000'),
    }

    trigger_url = f'{_url}/job/{_job}/buildWithParameters'

    try:
        response = requests.post(
            trigger_url,
            auth=(_user, _token),
            params=params,
            timeout=15,
        )
        response.raise_for_status()

        build_url = response.headers.get('Location', '')
        job.status = 'running'
        job.jenkins_url = build_url
        job.save(update_fields=['status', 'jenkins_url'])

        MLOpsConfig.objects.filter(standard=standard).update(
            last_trained_doc_count=doc_info.get('total_documents', 0),
            last_trained_at=tz.now(),
        )

        logger.info('Jenkins pipeline triggered for %s — job #%s', standard, job.id)
        return {
            'triggered':   True,
            'job_id':      job.id,
            'build_url':   build_url,
            'standard':    standard,
            'jenkins_url': _url,
        }

    except requests.RequestException as e:
        job.status = 'failed'
        job.log_output = str(e)
        job.end_time = tz.now()
        job.save(update_fields=['status', 'log_output', 'end_time'])
        logger.exception('Jenkins trigger failed')
        return {'triggered': False, 'reason': str(e), 'job_id': job.id}


# ── Job result callback ────────────────────────────────────────────────────────
def update_job_result(job_id: int, payload: Dict[str, Any]) -> bool:
    """Update a TrainingJob from a Jenkins webhook callback."""
    from api.models import TrainingJob, MLOpsConfig

    try:
        job = TrainingJob.objects.get(pk=job_id)
    except TrainingJob.DoesNotExist:
        logger.error('TrainingJob #%s not found', job_id)
        return False

    job.status          = payload.get('status', 'failed')
    # Only update numeric metrics when payload provides non-None values
    if payload.get('f1_score') is not None:
        job.f1_score        = float(payload['f1_score'])
    if payload.get('precision_score') is not None:
        job.precision_score = float(payload['precision_score'])
    if payload.get('recall_score') is not None:
        job.recall_score    = float(payload['recall_score'])
    if payload.get('drift_score') is not None:
        job.drift_score     = float(payload['drift_score'])
    if payload.get('avg_similarity') is not None:
        job.avg_similarity  = float(payload['avg_similarity'])
    if payload.get('accuracy') is not None:
        job.accuracy        = float(payload['accuracy'])

    # Clean model_version: strip "jenkins-0-" placeholder if present
    raw_version = payload.get('model_version', '') or ''
    if raw_version.startswith('jenkins-0-'):
        raw_version = raw_version[len('jenkins-0-'):]
    job.model_version   = raw_version

    job.drift_report    = payload.get('drift_report', {})
    job.log_output      = payload.get('log_output', '')
    job.end_time        = tz.now()
    job.save()

    if job.status == 'success' and job.standard:
        from django.db.models import F as _F
        MLOpsConfig.objects.filter(standard=job.standard).update(
            last_f1_score=job.f1_score,
            last_drift_score=job.drift_score,
            current_model_version=job.model_version or f'v{job.id}',
            last_trained_at=tz.now(),
            last_trained_doc_count=job.documents_count,
            dataset_size=job.documents_count,
            # FIX #9: increment training_count for Jenkins callback path
            training_count=_F('training_count') + 1,
        )

    logger.info('TrainingJob #%s updated to %s', job_id, job.status)
    return True


# ── Prometheus metrics ────────────────────────────────────────────────────────
def get_prometheus_metrics() -> str:
    """Return Prometheus text format metrics string."""
    from api.models import Document, TrainingJob, MLOpsConfig, RuleTrainingSample

    lines = [
        '# HELP compliance_documents_total Total documents',
        '# TYPE compliance_documents_total gauge',
        f'compliance_documents_total {Document.objects.count()}',
        '',
        '# HELP compliance_evidence_samples_total Total evidence samples',
        '# TYPE compliance_evidence_samples_total gauge',
        f'compliance_evidence_samples_total {RuleTrainingSample.objects.count()}',
        '',
        '# HELP compliance_training_jobs_total Total training jobs',
        '# TYPE compliance_training_jobs_total counter',
        f'compliance_training_jobs_total {TrainingJob.objects.count()}',
        '',
        '# HELP compliance_training_jobs_success Successful training jobs',
        '# TYPE compliance_training_jobs_success counter',
        f'compliance_training_jobs_success {TrainingJob.objects.filter(status="success").count()}',
        '',
        '# HELP compliance_training_jobs_failed Failed training jobs',
        '# TYPE compliance_training_jobs_failed counter',
        f'compliance_training_jobs_failed {TrainingJob.objects.filter(status="failed").count()}',
        '',
    ]

    for cfg in MLOpsConfig.objects.all():
        if cfg.last_f1_score is not None:
            lines += [
                f'# HELP compliance_model_f1_score F1 score of current model',
                f'# TYPE compliance_model_f1_score gauge',
                f'compliance_model_f1_score{{standard="{cfg.standard}"}} {cfg.last_f1_score}',
                '',
            ]
        if cfg.last_drift_score is not None:
            lines += [
                f'# HELP compliance_drift_score Current semantic drift score',
                f'# TYPE compliance_drift_score gauge',
                f'compliance_drift_score{{standard="{cfg.standard}"}} {cfg.last_drift_score}',
                '',
            ]

    latest = TrainingJob.objects.filter(status='success').order_by('-end_time').first()
    if latest and latest.end_time:
        ts = int(latest.end_time.timestamp() * 1000)
        lines += [
            '# HELP compliance_last_training_timestamp_ms Last successful training timestamp',
            '# TYPE compliance_last_training_timestamp_ms gauge',
            f'compliance_last_training_timestamp_ms {ts}',
            '',
        ]

    return '\n'.join(lines)
