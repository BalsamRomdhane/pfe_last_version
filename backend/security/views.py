"""
security/views.py — REST API for Document Security Analysis.

Endpoints (all require IsAuthenticated via DRF default):
  GET  /api/security/documents/<id>/analysis/      → retrieve analysis
  POST /api/security/documents/<id>/reanalyze/     → force re-run
  GET  /api/security/dashboard/                    → aggregated stats
  GET  /api/security/dashboard/statistics/         → detailed statistics
  GET  /api/security/dashboard/high-risk/          → high-risk document list
"""
from __future__ import annotations

import logging
from collections import Counter

from django.db.models import Avg, Count, Q, Sum
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authentication.permissions import IsAdmin, IsTeamLeadOrAdmin
from .models import DocumentSecurityAnalysis
from .serializers import DocumentSecurityAnalysisSerializer

logger = logging.getLogger(__name__)


# ── Helper: scope queryset by role ────────────────────────────────────────────

def _scoped_qs(request):
    """Return a DocumentSecurityAnalysis queryset scoped to the user's role."""
    from api.models import Document
    user  = request.user
    roles = [str(r).upper() for r in getattr(user, 'roles', []) or []]

    if 'ADMIN' in roles:
        return DocumentSecurityAnalysis.objects.select_related('document')

    if 'TEAMLEAD' in roles:
        dept = getattr(user, 'department', '') or ''
        return DocumentSecurityAnalysis.objects.filter(
            document__employee_department=dept
        ).select_related('document')

    # EMPLOYEE — own documents only
    return DocumentSecurityAnalysis.objects.filter(
        document__employee_username=user.username
    ).select_related('document')


# ── Document-level endpoints ──────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_security_analysis(request, document_id: int):
    """
    GET /api/security/documents/<id>/analysis/
    Retrieve the latest security analysis for a document.
    Returns 404 if no analysis exists yet (trigger via POST /reanalyze/).
    """
    from api.models import Document

    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return Response({'error': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Access control
    user  = request.user
    roles = [str(r).upper() for r in getattr(user, 'roles', []) or []]
    if 'ADMIN' not in roles and 'TEAMLEAD' not in roles:
        if document.employee_username != user.username:
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        analysis = DocumentSecurityAnalysis.objects.get(document=document)
    except DocumentSecurityAnalysis.DoesNotExist:
        return Response(
            {'error': 'No security analysis found. POST to /reanalyze/ to trigger one.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(DocumentSecurityAnalysisSerializer(analysis).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reanalyze_document_security(request, document_id: int):
    """
    POST /api/security/documents/<id>/reanalyze/
    Trigger (or force re-run) the security analysis for a document.
    """
    from api.models import Document
    from services.security_analysis import run_security_analysis

    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return Response({'error': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Only ADMIN / TEAMLEAD or the document owner may trigger analysis
    user  = request.user
    roles = [str(r).upper() for r in getattr(user, 'roles', []) or []]
    if 'ADMIN' not in roles and 'TEAMLEAD' not in roles:
        if document.employee_username != user.username:
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

    force   = request.data.get('force', False)
    analysis = run_security_analysis(document_id=document_id, force=bool(force))

    if analysis is None:
        return Response(
            {'error': 'Security analysis failed. Check server logs.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        DocumentSecurityAnalysisSerializer(analysis).data,
        status=status.HTTP_200_OK,
    )


# ── Dashboard endpoints ───────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeamLeadOrAdmin])
def security_dashboard(request):
    """
    GET /api/security/dashboard/
    Returns summary KPIs for the security dashboard widget.
    """
    qs = _scoped_qs(request)
    agg = qs.aggregate(
        total=Count('id'),
        high_risk=Count('id', filter=Q(risk_level__in=['HIGH', 'CRITICAL'])),
        critical=Count('id', filter=Q(risk_level='CRITICAL')),
        total_pii=Sum('pii_count'),
        total_secrets=Sum('secret_count'),
        avg_risk=Avg('risk_score'),
        avg_conf=Avg('confidentiality_score'),
    )

    return Response({
        'total_analysed':              agg['total'] or 0,
        'high_risk_count':             agg['high_risk'] or 0,
        'critical_risk_count':         agg['critical'] or 0,
        'total_pii_detected':          agg['total_pii'] or 0,
        'total_secrets_detected':      agg['total_secrets'] or 0,
        'avg_risk_score':              round(agg['avg_risk'] or 0, 1),
        'avg_confidentiality_score':   round(agg['avg_conf'] or 0, 1),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeamLeadOrAdmin])
def security_dashboard_statistics(request):
    """
    GET /api/security/dashboard/statistics/
    Detailed breakdown by confidentiality, risk, and GDPR status.
    Also returns top PII/secret types and a 30-day trend.
    """
    from django.utils import timezone
    from datetime import timedelta

    qs = _scoped_qs(request)

    # Distribution counts
    conf_dist = dict(
        qs.values('confidentiality_level')
        .annotate(n=Count('id'))
        .values_list('confidentiality_level', 'n')
    )
    risk_dist = dict(
        qs.values('risk_level')
        .annotate(n=Count('id'))
        .values_list('risk_level', 'n')
    )
    gdpr_dist = dict(
        qs.values('gdpr_status')
        .annotate(n=Count('id'))
        .values_list('gdpr_status', 'n')
    )

    # Aggregate PII / secret type counts from JSONField
    pii_counter: Counter = Counter()
    secret_counter: Counter = Counter()
    for row in qs.values('pii_types', 'secret_types'):
        if isinstance(row['pii_types'], dict):
            pii_counter.update(row['pii_types'])
        if isinstance(row['secret_types'], dict):
            secret_counter.update(row['secret_types'])

    # 30-day daily trend
    cutoff = timezone.now() - timedelta(days=30)
    trend  = (
        qs.filter(analysis_date__gte=cutoff)
        .extra(select={'day': "DATE(analysis_date)"})
        .values('day')
        .annotate(count=Count('id'), avg_risk=Avg('risk_score'))
        .order_by('day')
    )

    return Response({
        'confidentiality_distribution': conf_dist,
        'risk_distribution':            risk_dist,
        'gdpr_distribution':            gdpr_dist,
        'top_pii_types':     [{'type': k, 'count': v} for k, v in pii_counter.most_common(10)],
        'top_secret_types':  [{'type': k, 'count': v} for k, v in secret_counter.most_common(10)],
        'daily_trend':       list(trend),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeamLeadOrAdmin])
def security_dashboard_high_risk(request):
    """
    GET /api/security/dashboard/high-risk/
    Paginated list of high/critical risk documents with analysis summary.
    """
    qs = (
        _scoped_qs(request)
        .filter(risk_level__in=['HIGH', 'CRITICAL'])
        .order_by('-risk_score', '-analysis_date')
    )

    try:
        page      = max(1, int(request.query_params.get('page', 1)))
        page_size = min(50, int(request.query_params.get('page_size', 20)))
    except (TypeError, ValueError):
        page, page_size = 1, 20

    total  = qs.count()
    offset = (page - 1) * page_size
    items  = qs[offset:offset + page_size]

    return Response({
        'total':     total,
        'page':      page,
        'page_size': page_size,
        'results':   DocumentSecurityAnalysisSerializer(items, many=True).data,
    })
