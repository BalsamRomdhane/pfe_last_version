"""Compliance OS — Business Logic Services."""
from __future__ import annotations
import logging
from collections import Counter
from datetime import timedelta
from typing import Any, Dict, Optional

from django.db.models import Avg, Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def create_audit_log(entity_type, entity_id, action, performed_by,
                     old_value=None, new_value=None, reason='', request=None):
    from compliance.models import AuditLog
    try:
        ip, ua = None, ''
        if request:
            x = request.META.get('HTTP_X_FORWARDED_FOR')
            ip = x.split(',')[0].strip() if x else request.META.get('REMOTE_ADDR')
            ua = request.META.get('HTTP_USER_AGENT', '')[:512]
        AuditLog.objects.create(
            entity_type=str(entity_type), entity_id=str(entity_id), action=action,
            old_value=old_value, new_value=new_value, performed_by=str(performed_by),
            reason=reason, ip_address=ip, user_agent=ua,
        )
    except Exception as e:
        logger.error('Failed to create audit log: %s', e)


def compute_all_quality_scores(norme_id: Optional[int] = None) -> Dict[str, Any]:
    from api.models import RuleTrainingSample
    from compliance.models import EvidenceQualityScore
    qs = RuleTrainingSample.objects.select_related('document', 'norm', 'rule').all()
    if norme_id:
        qs = qs.filter(norm_id=norme_id)
    total, computed = qs.count(), 0
    level_counts = {'EXCELLENT': 0, 'GOOD': 0, 'WARNING': 0, 'POOR': 0}
    for ev in qs.iterator():
        try:
            s = EvidenceQualityScore.compute(ev)
            level_counts[s.quality_level] = level_counts.get(s.quality_level, 0) + 1
            computed += 1
        except Exception as e:
            logger.warning('Quality score failed for #%s: %s', ev.id, e)
    avg = (EvidenceQualityScore.objects.filter(evidence__norm_id=norme_id) if norme_id
           else EvidenceQualityScore.objects.all()).aggregate(avg=Avg('quality_score'))['avg'] or 0
    return {'total': total, 'computed': computed, 'level_distribution': level_counts, 'avg_quality_score': round(float(avg), 1)}


def compute_coverage(norme_id: int) -> Dict[str, Any]:
    from api.models import Norme, RuleTrainingSample
    from compliance.models import ComplianceCoverage, CriticalControl
    try:
        norme = Norme.objects.prefetch_related('rules').get(pk=norme_id)
    except Norme.DoesNotExist:
        return {'error': f'Norme {norme_id} not found'}
    all_rules = list(norme.rules.all())
    total = len(all_rules)
    if total == 0:
        return {'coverage_pct': 0, 'total_rules': 0, 'covered_rules': 0, 'norme_id': norme_id, 'norme_name': norme.name}
    covered_ids = set(RuleTrainingSample.objects.filter(norm=norme, label='approved')
                      .values_list('rule_id', flat=True).distinct())
    covered = len(covered_ids)
    uncovered = [r.title for r in all_rules if r.id not in covered_ids]
    critical_ids = set(CriticalControl.objects.filter(rule__norme=norme, is_critical=True)
                       .values_list('rule_id', flat=True))
    critical_total   = len(critical_ids)
    critical_covered = len(critical_ids & covered_ids)
    coverage_pct = round(covered / total * 100, 1)
    critical_pct = round(critical_covered / max(critical_total, 1) * 100, 1)
    ComplianceCoverage.objects.update_or_create(norme=norme, defaults={
        'total_rules': total, 'covered_rules': covered, 'critical_rules': critical_total,
        'critical_covered': critical_covered, 'coverage_pct': coverage_pct,
        'critical_pct': critical_pct, 'uncovered_rules': uncovered,
    })
    return {'norme_id': norme_id, 'norme_name': norme.name, 'total_rules': total,
            'covered_rules': covered, 'uncovered_rules': uncovered, 'coverage_pct': coverage_pct,
            'critical_rules': critical_total, 'critical_covered': critical_covered, 'critical_pct': critical_pct}


def compute_audit_readiness(norme_id: int) -> Dict[str, Any]:
    from api.models import Norme, RuleTrainingSample
    from compliance.models import AuditReadiness, EvidenceQualityScore
    try:
        norme = Norme.objects.get(pk=norme_id)
    except Norme.DoesNotExist:
        return {'error': f'Norme {norme_id} not found'}
    cov_data  = compute_coverage(norme_id)
    coverage_ok = cov_data.get('coverage_pct', 0) >= 90
    qs_all    = RuleTrainingSample.objects.filter(norm=norme)
    score_qs  = EvidenceQualityScore.objects.filter(evidence__norm=norme)
    avg_quality = score_qs.aggregate(avg=Avg('quality_score'))['avg'] or 0
    quality_ok  = float(avg_quality) >= 80
    expired_threshold = timezone.now() - timedelta(days=180)
    expired_count = qs_all.filter(updated_at__lt=expired_threshold).count()
    no_expired = expired_count == 0
    critical_gap_count = max(0, cov_data.get('critical_rules', 0) - cov_data.get('critical_covered', 0))
    no_critical_gaps = critical_gap_count == 0
    texts = list(qs_all.values_list('evidence_text', flat=True))
    non_empty = [t for t in texts if t and t.strip()]
    unique_count = len(set(non_empty))
    dup_rate = round((1 - unique_count / max(len(non_empty), 1)) * 100, 1) if non_empty else 0
    low_duplication = dup_rate < 5
    criteria = [coverage_ok, quality_ok, no_expired, no_critical_gaps, low_duplication]
    score = sum(20 for c in criteria if c)
    status = (AuditReadiness.Status.READY if score >= 80
              else AuditReadiness.Status.PARTIAL if score >= 40
              else AuditReadiness.Status.NOT_READY)
    AuditReadiness.objects.update_or_create(norme=norme, defaults={
        'score': float(score), 'status': status, 'coverage_ok': coverage_ok,
        'quality_ok': quality_ok, 'no_expired': no_expired, 'no_critical_gaps': no_critical_gaps,
        'low_duplication': low_duplication, 'avg_quality_score': float(avg_quality),
        'duplication_rate': dup_rate, 'expired_count': expired_count, 'critical_gap_count': critical_gap_count,
    })
    return {'norme_id': norme_id, 'norme_name': norme.name, 'score': score, 'status': status,
            'coverage_ok': coverage_ok, 'quality_ok': quality_ok, 'no_expired': no_expired,
            'no_critical_gaps': no_critical_gaps, 'low_duplication': low_duplication,
            'avg_quality_score': round(float(avg_quality), 1), 'duplication_rate': dup_rate,
            'expired_count': expired_count, 'critical_gap_count': critical_gap_count,
            'coverage_pct': cov_data.get('coverage_pct', 0)}


def compute_maturity(norme_id: int) -> Dict[str, Any]:
    from api.models import Norme
    from compliance.models import ComplianceCoverage, AuditReadiness, Risk, ComplianceMaturity, EvidenceQualityScore
    try:
        norme = Norme.objects.get(pk=norme_id)
    except Norme.DoesNotExist:
        return {'error': f'Norme {norme_id} not found'}
    try:
        cov = ComplianceCoverage.objects.get(norme=norme)
        coverage_score = cov.coverage_pct
    except ComplianceCoverage.DoesNotExist:
        coverage_score = compute_coverage(norme_id).get('coverage_pct', 0)
    avg_quality = EvidenceQualityScore.objects.filter(evidence__norm=norme).aggregate(avg=Avg('quality_score'))['avg'] or 0
    quality_score = float(avg_quality)
    try:
        ar = AuditReadiness.objects.get(norme=norme)
        readiness_score = ar.score
    except AuditReadiness.DoesNotExist:
        readiness_score = compute_audit_readiness(norme_id).get('score', 0)
    total_risks = Risk.objects.filter(standard=norme).count()
    open_risks  = Risk.objects.filter(standard=norme, status='OPEN').count()
    risk_score  = 100.0 if total_risks == 0 else (total_risks - open_risks) / total_risks * 100
    maturity_score = round(0.40*coverage_score + 0.25*quality_score + 0.20*readiness_score + 0.15*risk_score, 1)
    level = (ComplianceMaturity.Level.OPTIMIZED if maturity_score >= 81
             else ComplianceMaturity.Level.MANAGED if maturity_score >= 61
             else ComplianceMaturity.Level.DEVELOPING if maturity_score >= 41
             else ComplianceMaturity.Level.INITIAL)
    ComplianceMaturity.objects.update_or_create(norme=norme, defaults={
        'maturity_score': maturity_score, 'maturity_level': level,
        'coverage_score': coverage_score, 'quality_score': quality_score,
        'readiness_score': readiness_score, 'risk_score': risk_score,
    })
    return {'norme_id': norme_id, 'norme_name': norme.name, 'maturity_score': maturity_score,
            'maturity_level': level, 'coverage_score': round(coverage_score,1),
            'quality_score': round(quality_score,1), 'readiness_score': round(float(readiness_score),1),
            'risk_score': round(risk_score,1)}


def get_executive_dashboard() -> Dict[str, Any]:
    from api.models import Norme, RuleTrainingSample
    from compliance.models import Risk, EvidenceQualityScore
    norms = list(Norme.objects.prefetch_related('rules').all())
    norms_data, overall_coverage, overall_maturity, total_open_risks, total_expired = [], 0, 0, 0, 0
    expired_threshold = timezone.now() - timedelta(days=180)
    dup_texts = list(RuleTrainingSample.objects.exclude(evidence_text='').values_list('evidence_text', flat=True))
    dup_counter = Counter(dup_texts)
    duplicate_evidence = sum(v-1 for v in dup_counter.values() if v > 1)
    for norme in norms:
        cov = compute_coverage(norme.id)
        ar  = compute_audit_readiness(norme.id)
        mat = compute_maturity(norme.id)
        expired_count = RuleTrainingSample.objects.filter(norm=norme, updated_at__lt=expired_threshold).count()
        open_risks    = Risk.objects.filter(standard=norme, status='OPEN').count()
        critical_risks= Risk.objects.filter(standard=norme, status='OPEN', severity='CRITICAL').count()
        avg_q = EvidenceQualityScore.objects.filter(evidence__norm=norme).aggregate(avg=Avg('quality_score'))['avg'] or 0
        norms_data.append({
            'norme_id': norme.id, 'norme_name': norme.name,
            'coverage_pct': cov.get('coverage_pct', 0), 'uncovered_rules': cov.get('uncovered_rules', []),
            'critical_gaps': cov.get('critical_rules', 0) - cov.get('critical_covered', 0),
            'readiness_score': ar.get('score', 0), 'readiness_status': ar.get('status', 'NOT_READY'),
            'maturity_score': mat.get('maturity_score', 0), 'maturity_level': mat.get('maturity_level', 'INITIAL'),
            'avg_quality': round(float(avg_q), 1), 'open_risks': open_risks,
            'critical_risks': critical_risks, 'expired_evidence': expired_count,
        })
        overall_coverage += cov.get('coverage_pct', 0)
        overall_maturity += mat.get('maturity_score', 0)
        total_open_risks += open_risks
        total_expired    += expired_count
    n = max(len(norms), 1)
    overall_score = round(overall_maturity / n, 1)
    ready_count = sum(1 for nd in norms_data if nd['readiness_status'] == 'READY')
    overall_readiness = 'READY' if ready_count == n else 'PARTIAL' if ready_count > 0 else 'NOT_READY'
    return {
        'overall_compliance_score': overall_score,
        'overall_coverage_pct': round(overall_coverage / n, 1),
        'overall_maturity_score': round(overall_maturity / n, 1),
        'overall_readiness_status': overall_readiness,
        'total_open_risks': total_open_risks,
        'total_expired_evidence': total_expired,
        'total_duplicate_evidence': duplicate_evidence,
        'norms': norms_data,
        'computed_at': timezone.now().isoformat(),
    }
