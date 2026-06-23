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

import numpy as np
import requests
from django.conf import settings
from django.utils import timezone as tz

logger = logging.getLogger(__name__)

# ── Jenkins config from env ───────────────────────────────────────────────────
JENKINS_URL      = os.getenv('JENKINS_URL', 'http://jenkins:8080')
JENKINS_USER     = os.getenv('JENKINS_USER', 'admin')
JENKINS_TOKEN    = os.getenv('JENKINS_TOKEN', '')
JENKINS_JOB_NAME = os.getenv('JENKINS_JOB_NAME', 'compliance-ml-pipeline')
RETRAINING_THRESHOLD = int(os.getenv('MLOPS_RETRAINING_THRESHOLD', '10'))


# ── Document counting ─────────────────────────────────────────────────────────
def count_new_documents(standard: str) -> Dict[str, Any]:
    """Return count of documents added since last training for the given standard."""
    from api.models import Document, MLOpsConfig

    config, _ = MLOpsConfig.objects.get_or_create(
        standard=standard,
        defaults={'retraining_threshold': RETRAINING_THRESHOLD},
    )

    qs = Document.objects.filter(norme__name__iexact=standard)
    total = qs.count()

    if config.last_trained_at:
        new_docs = qs.filter(created_at__gt=config.last_trained_at).count()
    else:
        new_docs = total

    needs_training = (
        config.auto_trigger_enabled
        and new_docs >= config.retraining_threshold
    )

    return {
        'standard': standard,
        'total_documents': total,
        'new_documents': new_docs,
        'last_trained_at': config.last_trained_at.isoformat() if config.last_trained_at else None,
        'threshold': config.retraining_threshold,
        'needs_training': needs_training,
        'current_model_version': config.current_model_version,
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
        logger.error('Drift computation failed: %s', e)
        return {
            'drift_score': 0.0,
            'status': 'error',
            'message': str(e),
        }


# ── Jenkins trigger ───────────────────────────────────────────────────────────
def trigger_jenkins_pipeline(standard: str, doc_info: Dict[str, Any]) -> Dict[str, Any]:
    """POST to Jenkins to trigger the ML pipeline job."""
    from api.models import TrainingJob, MLOpsConfig

    if not JENKINS_TOKEN:
        logger.warning('JENKINS_TOKEN not configured — skipping Jenkins trigger.')
        return {'triggered': False, 'reason': 'JENKINS_TOKEN not configured'}

    job = TrainingJob.objects.create(
        status='pending',
        standard=standard,
        documents_count=doc_info.get('total_documents', 0),
        new_docs_since=doc_info.get('new_documents', 0),
        triggered_by='auto',
    )

    params = {
        'STANDARD': standard,
        'DOCUMENT_COUNT': str(doc_info.get('total_documents', 0)),
        'NEW_DOCS': str(doc_info.get('new_documents', 0)),
        'JOB_ID': str(job.id),
        'API_URL': os.getenv('DJANGO_API_URL', 'http://backend:8000'),
    }

    url = f"{JENKINS_URL}/job/{JENKINS_JOB_NAME}/buildWithParameters"

    try:
        response = requests.post(
            url,
            auth=(JENKINS_USER, JENKINS_TOKEN),
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
            'triggered': True,
            'job_id': job.id,
            'build_url': build_url,
            'standard': standard,
        }

    except requests.RequestException as e:
        job.status = 'failed'
        job.log_output = str(e)
        job.end_time = tz.now()
        job.save(update_fields=['status', 'log_output', 'end_time'])
        logger.error('Jenkins trigger failed: %s', e)
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
    job.f1_score        = payload.get('f1_score')
    job.precision_score = payload.get('precision_score')
    job.recall_score    = payload.get('recall_score')
    job.drift_score     = payload.get('drift_score')
    job.avg_similarity  = payload.get('avg_similarity')
    job.model_version   = payload.get('model_version', '')
    job.drift_report    = payload.get('drift_report', {})
    job.log_output      = payload.get('log_output', '')
    job.end_time        = tz.now()
    job.save()

    if job.status == 'success' and job.standard:
        MLOpsConfig.objects.filter(standard=job.standard).update(
            last_f1_score=job.f1_score,
            last_drift_score=job.drift_score,
            current_model_version=job.model_version or f'v{job.id}',
            last_trained_at=tz.now(),
            last_trained_doc_count=job.documents_count,
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
