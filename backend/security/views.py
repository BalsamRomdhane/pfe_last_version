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
from .serializers import DocumentSecurityAnalysisSerializer, DocumentIntegritySerializer

logger = logging.getLogger(__name__)


# ── RBAC helper ───────────────────────────────────────────────────────────────

def _check_document_access(request, document) -> Response | None:
    """
    Verify the caller may access ``document``.

    Returns None if access is granted.
    Returns a DRF Response (403) if access is denied.

    Rules
    -----
    ADMIN      → all documents
    TEAMLEAD   → own department only (empty dept string = allowed)
    EMPLOYEE   → own documents only
    """
    user  = request.user
    roles = [str(r).upper() for r in getattr(user, 'roles', []) or []]

    if 'ADMIN' in roles:
        return None

    if 'TEAMLEAD' in roles:
        dept = getattr(user, 'department', '') or ''
        if document.employee_department and document.employee_department != dept:
            return Response(
                {'error': 'You can only access documents from your department.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    # EMPLOYEE
    if document.employee_username != user.username:
        return Response(
            {'error': 'You can only access your own documents.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


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
def document_secure_download(request, document_id: int):
    """
    GET /api/security/documents/<id>/download/

    Download a document with RBAC, in-memory decryption, and optional watermark.

    Query parameters
    ----------------
    watermark=true   Apply a watermark to the downloaded file (default: true).
                     Pass watermark=false to skip watermarking.

    Security guarantees
    -------------------
    1. RBAC:         Same rules as secure_view (owner / dept TeamLead / Admin).
    2. In-memory:    Encrypted docs decrypted in memory — no plaintext on disk.
    3. Watermark:    Downloaded by / Date / Time / Classification stamped in.
    4. Disposition:  Content-Disposition: attachment (forces download dialog).
    5. No-cache:     Cache-Control: no-store prevents browser caching.

    Watermark content (PDF diagonal stamp / DOCX header paragraph)
    ---------------------------------------------------------------
    Downloaded by: <username>
    Date:          <YYYY-MM-DD>
    Time:          <HH:MM UTC>
    Classification: <level>

    Error responses
    ---------------
    404  document not found
    403  RBAC denied / encryption key missing
    422  document has no file
    500  read / watermark failure
    """
    import mimetypes
    from django.http import HttpResponse
    from api.models import Document
    from services.document_storage import DocumentStorageService
    from services.security.watermark import WatermarkInfo, add_watermark

    # ── Fetch document ────────────────────────────────────────────────────────
    try:
        document = Document.objects.select_related('norme').get(pk=document_id)
    except Document.DoesNotExist:
        return Response(
            {'error': f'Document #{document_id} not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # ── RBAC ─────────────────────────────────────────────────────────────────
    denied = _check_document_access(request, document)
    if denied:
        return denied

    # ── Check file ────────────────────────────────────────────────────────────
    if not document.file or not document.file.name:
        return Response(
            {'error': 'Document has no file attached.'},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # ── Determine MIME type and filename ─────────────────────────────────────
    filename  = DocumentStorageService.get_filename(document_id) or 'document'
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        lower = filename.lower()
        if lower.endswith('.pdf'):
            mime_type = 'application/pdf'
        elif lower.endswith('.docx'):
            mime_type = (
                'application/vnd.openxmlformats-officedocument'
                '.wordprocessingml.document'
            )
        else:
            mime_type = 'application/octet-stream'

    # ── Read plaintext (decrypt in memory if encrypted) ───────────────────────
    try:
        plaintext = DocumentStorageService.read_plaintext(document_id)
    except PermissionError as exc:
        logger.warning(
            'secure_download: encryption key missing for Document #%s — %s',
            document_id, exc,
        )
        return Response(
            {'error': 'This document is encrypted and the decryption key is not available.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if plaintext is None:
        logger.error('secure_download: read_plaintext returned None for Document #%s', document_id)
        return Response(
            {'error': 'Could not read document file. Check server logs.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # ── Watermark (optional — enabled by default) ─────────────────────────────
    apply_watermark = request.query_params.get('watermark', 'true').lower() not in ('false', '0', 'no')

    if apply_watermark:
        try:
            # Determine classification for watermark label
            classification = 'INTERNAL'
            try:
                from security.models import DocumentSecurityAnalysis
                analysis = DocumentSecurityAnalysis.objects.get(document=document)
                classification = analysis.confidentiality_level or 'INTERNAL'
            except Exception:
                pass

            wm_info = WatermarkInfo(
                username=getattr(request.user, 'username', 'unknown'),
                classification=classification,
            )
            content = add_watermark(plaintext, filename, wm_info)
        except Exception as exc:
            logger.warning(
                'secure_download: watermark failed for Document #%s — %s. '
                'Serving without watermark.',
                document_id, exc,
            )
            content = plaintext
    else:
        content = plaintext

    # ── Build download response ───────────────────────────────────────────────
    response = HttpResponse(content, content_type=mime_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Content-Length']      = len(content)
    response['Cache-Control']       = 'no-store, no-cache, must-revalidate, private'
    response['Pragma']              = 'no-cache'
    response['X-Content-Type-Options'] = 'nosniff'

    logger.info(
        'secure_download: Document #%s served to "%s" '
        '(encrypted=%s, watermark=%s, size=%d bytes)',
        document_id,
        getattr(request.user, 'username', '?'),
        document.encrypted,
        apply_watermark,
        len(content),
    )

    # ── Audit log (Phase 8) ───────────────────────────────────────────────────
    try:
        from services.security.document_audit import DocumentAuditService
        DocumentAuditService.log(
            action=DocumentAuditService.DOWNLOAD,
            document_id=document_id,
            username=getattr(request.user, 'username', 'unknown'),
            request=request,
            encrypted=document.encrypted,
            watermark_applied=apply_watermark,
            file_size_bytes=len(content),
        )
    except Exception:
        pass

    # Explicitly delete the plaintext reference from local scope
    del plaintext

    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_secure_view(request, document_id: int):
    """
    GET /api/security/documents/<id>/view/

    Serve a document file through a secure, authenticated, RBAC-checked
    streaming response.

    Security guarantees
    -------------------
    1. RBAC:       Only the owner (EMPLOYEE), their TeamLead, or ADMIN can view.
    2. Dept check: TeamLeads can only view documents from their department.
    3. In-memory:  Encrypted documents are decrypted entirely in memory via
                   DocumentStorageService.open_plaintext_stream(). The plaintext
                   is NEVER written to disk — it exists only for the duration of
                   this request and is garbage-collected when the response is sent.
    4. No /media/: The file is never served from the /media/ URL directly.
                   This endpoint is the only authorised path to the content.

    Response
    --------
    - Content-Type is inferred from the file extension (pdf → application/pdf,
      docx → application/vnd.openxmlformats-officedocument.wordprocessingml.document).
    - Content-Disposition: inline (view in browser, not download).
    - For encrypted documents: the response body is decrypted plaintext bytes.
    - For plain documents: the response body is read from disk via StorageService.

    Error responses
    ---------------
    404  document not found
    403  access denied (RBAC / dept)
    403  encryption key missing (PermissionError from StorageService)
    422  document has no file
    500  read / decryption failure
    """
    import mimetypes
    from django.http import FileResponse, HttpResponse
    from api.models import Document
    from services.document_storage import DocumentStorageService

    # ── Fetch document ────────────────────────────────────────────────────────
    try:
        document = Document.objects.select_related('norme').get(pk=document_id)
    except Document.DoesNotExist:
        return Response(
            {'error': f'Document #{document_id} not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # ── RBAC ─────────────────────────────────────────────────────────────────
    denied = _check_document_access(request, document)
    if denied:
        return denied

    # ── Check file exists ─────────────────────────────────────────────────────
    if not document.file or not document.file.name:
        return Response(
            {'error': 'Document has no file attached.'},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # ── Determine MIME type ───────────────────────────────────────────────────
    filename  = DocumentStorageService.get_filename(document_id) or 'document'
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        # Fall back by extension
        lower = filename.lower()
        if lower.endswith('.pdf'):
            mime_type = 'application/pdf'
        elif lower.endswith('.docx'):
            mime_type = (
                'application/vnd.openxmlformats-officedocument'
                '.wordprocessingml.document'
            )
        else:
            mime_type = 'application/octet-stream'

    # ── Open plaintext stream (decrypt in memory if encrypted) ───────────────
    try:
        stream = DocumentStorageService.open_plaintext_stream(document_id)
    except PermissionError as exc:
        logger.warning(
            'secure_view: encryption key missing for Document #%s — %s',
            document_id, exc,
        )
        return Response(
            {'error': 'This document is encrypted and the decryption key is not available.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if stream is None:
        logger.error('secure_view: StorageService returned None for Document #%s', document_id)
        return Response(
            {'error': 'Could not read document file. Check server logs.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # ── Build response ────────────────────────────────────────────────────────
    # FileResponse wraps the BytesIO and sends it as a streaming response.
    # Content-Disposition: inline → opens in browser tab (not a download).
    # The stream (and its plaintext bytes) is garbage-collected by Python
    # immediately after the response is fully sent.
    response = FileResponse(
        stream,
        content_type=mime_type,
        as_attachment=False,
    )
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    # Security headers: prevent the browser from caching sensitive content
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response['Pragma']        = 'no-cache'
    response['X-Content-Type-Options'] = 'nosniff'

    logger.info(
        'secure_view: Document #%s served to user "%s" (encrypted=%s)',
        document_id,
        getattr(request.user, 'username', '?'),
        document.encrypted,
    )

    # ── Audit log (Phase 8) ───────────────────────────────────────────────────
    try:
        from services.security.document_audit import DocumentAuditService
        DocumentAuditService.log(
            action=DocumentAuditService.VIEW,
            document_id=document_id,
            username=getattr(request.user, 'username', 'unknown'),
            request=request,
            encrypted=document.encrypted,
            classification=getattr(
                getattr(document, 'security_analysis', None),
                'confidentiality_level', 'UNKNOWN'
            ),
        )
    except Exception:
        pass  # audit failure must never block the response

    return response


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


# ── Phase 8 — Document audit history ─────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_audit_history(request, document_id: int):
    """
    GET /api/security/documents/<id>/audit/

    Return the full audit trail for a document — all security actions
    logged via DocumentAuditService (VIEW, DOWNLOAD, INTEGRITY_CHECK, etc.).

    Access control
    --------------
    ADMIN      : any document
    TEAMLEAD   : department documents only
    EMPLOYEE   : own documents only

    Response
    --------
    [
      {
        "id":           1,
        "action":       "VIEW",
        "performed_by": "alice",
        "performed_at": "2026-07-01T10:23:00Z",
        "ip_address":   "192.168.1.1",
        "new_value":    { "document_id": 42, "encrypted": true, ... },
        "reason":       ""
      },
      ...
    ]
    """
    from api.models import Document
    from services.security.document_audit import DocumentAuditService

    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        return Response(
            {'error': f'Document #{document_id} not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    denied = _check_document_access(request, document)
    if denied:
        return denied

    history = DocumentAuditService.get_document_history(document_id=document_id)
    return Response(history)


# ── Phase 11 — Admin Security Dashboard enriched endpoint ────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeamLeadOrAdmin])
def security_dashboard_admin(request):
    """
    GET /api/security/dashboard/admin/

    Enriched Admin Security Dashboard data.

    Returns:
      - KPI summary (total analysed, encrypted, PII, secrets, high-risk)
      - Classification distribution (for pie chart)
      - Risk distribution (for bar chart)
      - Encryption stats (encrypted vs plaintext)
      - Integrity stats (verified vs pending)
      - Recent audit events (last 20 document security actions)
      - 30-day trend (daily analysis count + avg risk score)
    """
    from django.utils import timezone
    from datetime import timedelta
    from api.models import Document
    from services.security.document_audit import DocumentAuditService

    qs = _scoped_qs(request)

    # ── KPI aggregate ─────────────────────────────────────────────────────────
    agg = qs.aggregate(
        total_analysed=Count('id'),
        total_pii=Sum('pii_count'),
        total_secrets=Sum('secret_count'),
        high_risk=Count('id', filter=Q(risk_level__in=['HIGH', 'CRITICAL'])),
        critical=Count('id', filter=Q(risk_level='CRITICAL')),
        avg_risk=Avg('risk_score'),
        avg_conf=Avg('confidentiality_score'),
    )

    # ── Encrypted documents count ─────────────────────────────────────────────
    user  = request.user
    roles = [str(r).upper() for r in getattr(user, 'roles', []) or []]
    doc_qs = Document.objects.all() if 'ADMIN' in roles else \
             Document.objects.filter(employee_department=getattr(user, 'department', '') or '')
    total_docs      = doc_qs.count()
    encrypted_docs  = doc_qs.filter(encrypted=True).count()
    hashed_docs     = doc_qs.exclude(sha256_hash='').count()

    # ── Classification distribution ───────────────────────────────────────────
    conf_dist = dict(
        qs.values('confidentiality_level')
        .annotate(n=Count('id'))
        .values_list('confidentiality_level', 'n')
    )

    # ── Risk distribution ─────────────────────────────────────────────────────
    risk_dist = dict(
        qs.values('risk_level')
        .annotate(n=Count('id'))
        .values_list('risk_level', 'n')
    )

    # ── GDPR distribution ─────────────────────────────────────────────────────
    gdpr_dist = dict(
        qs.values('gdpr_status')
        .annotate(n=Count('id'))
        .values_list('gdpr_status', 'n')
    )

    # ── Top PII and secret types ──────────────────────────────────────────────
    pii_counter: Counter = Counter()
    secret_counter: Counter = Counter()
    for row in qs.values('pii_types', 'secret_types'):
        if isinstance(row['pii_types'], dict):
            pii_counter.update(row['pii_types'])
        if isinstance(row['secret_types'], dict):
            secret_counter.update(row['secret_types'])

    # ── 30-day trend ──────────────────────────────────────────────────────────
    cutoff = timezone.now() - timedelta(days=30)
    trend = (
        qs.filter(analysis_date__gte=cutoff)
        .extra(select={'day': "DATE(analysis_date)"})
        .values('day')
        .annotate(count=Count('id'), avg_risk=Avg('risk_score'))
        .order_by('day')
    )

    # ── Recent document security audit events ─────────────────────────────────
    recent_audit = DocumentAuditService.get_recent_actions(limit=20)

    return Response({
        # KPIs
        'total_documents':      total_docs,
        'total_analysed':       agg['total_analysed'] or 0,
        'encrypted_count':      encrypted_docs,
        'plaintext_count':      total_docs - encrypted_docs,
        'hashed_count':         hashed_docs,
        'total_pii_detected':   agg['total_pii'] or 0,
        'total_secrets':        agg['total_secrets'] or 0,
        'high_risk_count':      agg['high_risk'] or 0,
        'critical_count':       agg['critical'] or 0,
        'avg_risk_score':       round(agg['avg_risk'] or 0, 1),
        'avg_conf_score':       round(agg['avg_conf'] or 0, 1),
        # Distributions
        'classification_dist':  conf_dist,
        'risk_dist':            risk_dist,
        'gdpr_dist':            gdpr_dist,
        # Encryption
        'encryption_stats': {
            'encrypted':  encrypted_docs,
            'plaintext':  total_docs - encrypted_docs,
            'total':      total_docs,
            'pct':        round(encrypted_docs / max(total_docs, 1) * 100, 1),
        },
        # Integrity
        'integrity_stats': {
            'hashed':   hashed_docs,
            'no_hash':  total_docs - hashed_docs,
            'total':    total_docs,
            'pct':      round(hashed_docs / max(total_docs, 1) * 100, 1),
        },
        # Top types
        'top_pii_types':    [{'type': k, 'count': v} for k, v in pii_counter.most_common(8)],
        'top_secret_types': [{'type': k, 'count': v} for k, v in secret_counter.most_common(8)],
        # Trend
        'daily_trend':      list(trend),
        # Audit history
        'recent_audit':     recent_audit,
    })


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
        'id', 'status', 'employee_username', 'employee_department', 'created_at', 'file'
    )[:200]

    # Build display label from file name + norme (file is a FieldFile path string)
    results = []
    for doc in qs:
        file_path = doc.get('file') or ''
        # file path is like "documents/myfile.pdf" — extract basename
        filename = file_path.split('/')[-1].split('\\')[-1] if file_path else ''
        results.append({
            'id':                 doc['id'],
            'label':              filename or f'Document #{doc["id"]}',
            'status':             doc.get('status') or '',
            'employee_username':  doc.get('employee_username') or '',
            'employee_department': doc.get('employee_department') or '',
            'created_at':         doc.get('created_at'),
        })

    return Response(results)


# ── Phase 2 — Integrity verification endpoint ────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_integrity_check(request, document_id: int):
    """
    GET /api/security/documents/<id>/integrity/

    Verify the SHA-256 integrity of a stored document.

    Returns a JSON payload describing whether the file currently on storage
    matches the hash that was recorded when the document was uploaded.

    Access control
    --------------
    - ADMIN      : any document
    - TEAMLEAD   : documents from their department only
    - EMPLOYEE   : their own documents only

    Response shape  (see DocumentIntegritySerializer for field docs)
    ---------------
    {
      "document_id":     42,
      "is_valid":        true,
      "status":          "VERIFIED",
      "stored_hash":     "a3f1...",
      "computed_hash":   "a3f1...",
      "hash_algorithm":  "sha256",
      "hash_created_at": "2026-07-01T10:23:00Z",
      "reason":          "File integrity verified — hash matches."
    }

    Status values
    -------------
    VERIFIED      — file matches stored hash
    TAMPERED      — hashes differ (integrity violation)
    PENDING       — no hash stored yet (pipeline still running)
    FILE_MISSING  — hash stored but file not found on storage
    NOT_FOUND     — document PK does not exist
    """
    from api.models import Document
    from services.security.hashing import DocumentIntegrityService

    # ── Fetch document ────────────────────────────────────────────────────────
    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        payload = {
            'document_id':     document_id,
            'is_valid':        False,
            'status':          'NOT_FOUND',
            'stored_hash':     '',
            'computed_hash':   '',
            'hash_algorithm':  '',
            'hash_created_at': None,
            'reason':          f'Document #{document_id} not found.',
        }
        return Response(
            DocumentIntegritySerializer(payload).data,
            status=status.HTTP_404_NOT_FOUND,
        )

    # ── RBAC ─────────────────────────────────────────────────────────────────
    user  = request.user
    roles = [str(r).upper() for r in getattr(user, 'roles', []) or []]

    if 'ADMIN' not in roles:
        if 'TEAMLEAD' in roles:
            dept = getattr(user, 'department', '') or ''
            if document.employee_department and document.employee_department != dept:
                return Response(
                    {'error': 'You can only check integrity for documents in your department.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            # EMPLOYEE or unknown role
            if document.employee_username != user.username:
                return Response(
                    {'error': 'You can only check integrity for your own documents.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

    # ── Run integrity check ───────────────────────────────────────────────────
    result = DocumentIntegrityService.verify_document(document_id=document_id)

    # ── Derive a clean status string from the result ──────────────────────────
    if result.reason == 'Document not found.':
        integrity_status = 'NOT_FOUND'
    elif 'No integrity hash' in result.reason:
        integrity_status = 'PENDING'
    elif 'File not found' in result.reason:
        integrity_status = 'FILE_MISSING'
    elif result.is_valid:
        integrity_status = 'VERIFIED'
    else:
        integrity_status = 'TAMPERED'

    payload = {
        'document_id':     result.document_id,
        'is_valid':        result.is_valid,
        'status':          integrity_status,
        'stored_hash':     result.stored_hash,
        'computed_hash':   result.computed_hash,
        'hash_algorithm':  document.hash_algorithm or 'sha256',
        'hash_created_at': document.hash_created_at,
        'reason':          result.reason,
    }

    http_status = (
        status.HTTP_200_OK
        if integrity_status in ('VERIFIED', 'PENDING', 'FILE_MISSING')
        else status.HTTP_409_CONFLICT  # TAMPERED is a conflict with expected state
    )

    # ── Audit log (Phase 8) ───────────────────────────────────────────────────
    try:
        from services.security.document_audit import DocumentAuditService
        DocumentAuditService.log(
            action=DocumentAuditService.INTEGRITY_CHECK,
            document_id=document_id,
            username=getattr(request.user, 'username', 'unknown'),
            request=request,
            integrity_status=integrity_status,
            is_valid=result.is_valid,
        )
    except Exception:
        pass

    return Response(DocumentIntegritySerializer(payload).data, status=http_status)


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
