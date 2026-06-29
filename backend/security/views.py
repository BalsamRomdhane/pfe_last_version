"""
security/views.py — REST API for Document Security Analysis.

Endpoints (all require IsAuthenticated via DRF default):
  GET  /api/security/documents/<id>/analysis/      → retrieve analysis
  POST /api/security/documents/<id>/reanalyze/     → force re-run
  POST /api/security/scan/                         → scan an uploaded file (no DB save)
  GET  /api/security/documents/list/               → list documents for dropdown
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


# ── Document list for dropdown ────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def documents_list_for_security(request):
    """
    GET /api/security/documents/list/
    Returns a lightweight list of documents scoped by role,
    used to populate the Document Security dropdown.
    """
    from api.models import Document

    user  = request.user
    roles = [str(r).upper() for r in getattr(user, 'roles', []) or []]

    if 'ADMIN' in roles:
        qs = Document.objects.all()
    elif 'TEAMLEAD' in roles:
        dept = getattr(user, 'department', '') or ''
        qs = Document.objects.filter(employee_department=dept)
    else:
        qs = Document.objects.filter(employee_username=user.username)

    qs = qs.order_by('-created_at').values(
        'id', 'title', 'status', 'employee_username', 'created_at'
    )[:200]

    return Response(list(qs))


# ── Scan uploaded file (no DB save) ──────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scan_uploaded_file(request):
    """
    POST /api/security/scan/
    Accepts a multipart file upload and runs the full security analysis
    pipeline in-memory without saving the document to the database.

    Returns the same analysis payload as document_security_analysis,
    minus the 'document' FK field.
    """
    import io

    uploaded = request.FILES.get('file')
    if not uploaded:
        return Response({'error': 'No file provided. Send a multipart/form-data request with field "file".'}, status=400)

    allowed_ext = ('.pdf', '.docx', '.txt')
    fname = uploaded.name.lower()
    if not any(fname.endswith(ext) for ext in allowed_ext):
        return Response({'error': 'Unsupported file type. Only PDF, DOCX and TXT are supported.'}, status=400)

    max_mb = 20
    if uploaded.size > max_mb * 1024 * 1024:
        return Response({'error': f'File too large. Maximum size is {max_mb} MB.'}, status=400)

    # ── Read file content ────────────────────────────────────────────────
    file_content = uploaded.read()

    # ── Extract text ──────────────────────────────────────────────────────
    text = ''
    try:
        if fname.endswith('.txt'):
            text = file_content.decode('utf-8', errors='ignore')
        else:
            from api.utils import extract_text
            file_like = io.BytesIO(file_content)
            file_like.name = uploaded.name
            text = extract_text(file_like)
    except Exception as exc:
        logger.warning('scan_uploaded_file: text extraction failed for %s: %s', uploaded.name, exc)

    text_lower = text.lower()

    # ── Run all detectors ─────────────────────────────────────────────────
    from services.security.pii_detector        import detect_pii, count_pii_by_type
    from services.security.secret_detector     import detect_secrets, count_secrets_by_type
    from services.security.metadata_analyzer   import analyze_metadata
    from services.security.risk_scoring        import compute_scores
    from services.security.gdpr_checker        import check_gdpr
    from services.security.recommendation_engine import generate_recommendations

    pii_matches    = detect_pii(text)
    pii_counts     = count_pii_by_type(pii_matches)
    secret_matches = detect_secrets(text)
    secret_counts  = count_secrets_by_type(secret_matches)

    metadata_result = analyze_metadata(file_content, uploaded.name)
    metadata_risk   = metadata_result.metadata_risk_score if metadata_result else 0

    financial_detected = any(kw in text_lower for kw in {
        'salary', 'salaire', 'payroll', 'iban', 'financial', 'financier', 'budget', 'invoice', 'facture',
    })
    hr_detected = any(kw in text_lower for kw in {
        'employee', 'employé', 'hr', 'rh', 'human resources', 'ressources humaines', 'personnel',
    })

    score_result = compute_scores(
        pii_matches=pii_matches,
        secret_matches=secret_matches,
        text_lower=text_lower,
        metadata_risk_score=metadata_risk,
    )
    gdpr_result = check_gdpr(
        text_lower=text_lower,
        pii_count=len(pii_matches),
        secret_count=len(secret_matches),
        pii_matches=pii_matches,
    )
    rec_list = generate_recommendations(
        pii_count=len(pii_matches),
        pii_types=pii_counts,
        secret_count=len(secret_matches),
        secret_types=secret_counts,
        confidentiality_level=score_result.confidentiality_level,
        risk_level=score_result.risk_level,
        gdpr_status=gdpr_result.gdpr_status,
        metadata_risk_score=metadata_risk,
        financial_detected=financial_detected,
        hr_detected=hr_detected,
        hidden_content=metadata_result.hidden_text_detected if metadata_result else False,
    )

    # ── Build response (same shape as DocumentSecurityAnalysisSerializer) ─
    return Response({
        'filename':               uploaded.name,
        'file_size_kb':           round(uploaded.size / 1024, 1),
        'pii_count':              len(pii_matches),
        'pii_types':              pii_counts,
        'pii_details':            [{'type': m.pii_type, 'value': m.value, 'context': m.context} for m in pii_matches],
        'secret_count':           len(secret_matches),
        'secret_types':           secret_counts,
        'secret_details':         [{'type': m.secret_type, 'value': m.value, 'confidence': m.confidence, 'context': m.context} for m in secret_matches],
        'financial_data_detected': financial_detected,
        'employee_data_detected':  hr_detected,
        'metadata_risk':           metadata_risk,
        'metadata_details': {
            'author':         metadata_result.author           if metadata_result else None,
            'company':        metadata_result.company          if metadata_result else None,
            'software':       metadata_result.software         if metadata_result else None,
            'created_at':     metadata_result.created_at       if metadata_result else None,
            'modified_at':    metadata_result.modified_at      if metadata_result else None,
            'version':        metadata_result.version          if metadata_result else None,
            'hidden_content': metadata_result.hidden_text_detected if metadata_result else False,
            'risk_flags':     metadata_result.risk_flags       if metadata_result else [],
        } if metadata_result else {},
        'confidentiality_level':  score_result.confidentiality_level,
        'confidentiality_score':  score_result.confidentiality_score,
        'risk_score':             score_result.risk_score,
        'risk_level':             score_result.risk_level,
        'score_breakdown':        score_result.score_breakdown,
        'score_explanation':      score_result.explanation,
        'gdpr_status':            gdpr_result.gdpr_status,
        'gdpr_has_pii':           gdpr_result.has_pii,
        'gdpr_has_sensitive':     gdpr_result.has_sensitive_data,
        'gdpr_has_financial':     gdpr_result.has_financial_data,
        'gdpr_issues':            gdpr_result.issues,
        'gdpr_compliance_summary': gdpr_result.compliance_summary,
        'recommendations':        [
            {'priority': r.priority, 'category': r.category,
             'title': r.title, 'description': r.description, 'action': r.action}
            for r in rec_list
        ],
        'is_high_risk':  score_result.risk_level in ('HIGH', 'CRITICAL'),
        'has_secrets':   len(secret_matches) > 0,
        'analysis_version': '1.0.0',
        'scanned_at':    None,   # ephemeral — not persisted
    })
