"""
security_analysis.py — Document Security Analysis orchestrator.

This service coordinates all sub-detectors and writes the result to the
DocumentSecurityAnalysis model.  It is the single entry point called by
views and signals — callers must never import sub-detectors directly.

Architecture
------------
                    ┌────────────────────────┐
                    │   security_analysis.py  │  ← orchestrator
                    └───────────┬────────────┘
              ┌────────┬────────┼───────────┬──────────┐
              ▼        ▼        ▼           ▼          ▼
        pii_detector  secret  metadata  risk_scoring  gdpr
                      _detect  _analyzer            _checker
                                                        │
                                               recommendation
                                                   _engine
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from django.utils import timezone

if TYPE_CHECKING:
    pass

from .security.pii_detector         import detect_pii,     count_pii_by_type
from .security.secret_detector      import detect_secrets,  count_secrets_by_type
from .security.metadata_analyzer    import analyze_metadata
from .security.risk_scoring         import compute_scores
from .security.gdpr_checker         import check_gdpr
from .security.recommendation_engine import generate_recommendations

logger = logging.getLogger(__name__)

# Current analysis version — bump when detection patterns change
ANALYSIS_VERSION = '1.0.0'


def run_security_analysis(document_id: int, force: bool = False) -> Optional[object]:
    """
    Run the full security analysis pipeline for a given Document.

    Parameters
    ----------
    document_id : int
        Primary key of the api.Document to analyse.
    force : bool
        If True, re-run even if a recent result already exists.

    Returns
    -------
    DocumentSecurityAnalysis instance or None on error.
    """
    # Lazy imports to avoid circular dependencies at module load time
    from api.models import Document
    from security.models import DocumentSecurityAnalysis

    try:
        document = Document.objects.select_related('norme').get(pk=document_id)
    except Document.DoesNotExist:
        logger.error('security_analysis: Document #%s not found', document_id)
        return None

    # Skip if a fresh result already exists (unless forced)
    if not force:
        existing = DocumentSecurityAnalysis.objects.filter(
            document=document,
            analysis_version=ANALYSIS_VERSION,
        ).first()
        if existing:
            logger.debug(
                'security_analysis: Document #%s already has v%s result — skipping',
                document_id, ANALYSIS_VERSION,
            )
            return existing

    # ── Extract text and binary content ───────────────────────────────────────
    # Phase 5 — all file I/O goes through DocumentStorageService.
    # read_raw() returns the bytes on disk (plaintext before Phase 4 encryption,
    # ciphertext after). For security_analysis the content must be PLAINTEXT so
    # we use read_plaintext() which transparently decrypts if needed.
    text = ''
    file_content = b''
    filename = ''

    if document.file:
        try:
            from services.document_storage import DocumentStorageService
            filename = DocumentStorageService.get_filename(document_id) or document.file.name or ''
            file_content = DocumentStorageService.read_plaintext(document_id) or b''
        except PermissionError as exc:
            logger.warning('security_analysis: decryption key missing for doc #%s: %s', document_id, exc)
        except Exception as exc:
            logger.warning('security_analysis: could not read file for doc #%s: %s', document_id, exc)

        if file_content:
            try:
                from api.utils import extract_text
                import io
                file_like = io.BytesIO(file_content)
                file_like.name = filename
                text = extract_text(file_like)
            except Exception as exc:
                logger.warning('security_analysis: text extraction failed for doc #%s: %s', document_id, exc)

    text_lower = text.lower()

    # ── PII detection ─────────────────────────────────────────────────────────
    pii_matches = detect_pii(text)
    pii_counts  = count_pii_by_type(pii_matches)

    # ── Secret detection ──────────────────────────────────────────────────────
    secret_matches = detect_secrets(text)
    secret_counts  = count_secrets_by_type(secret_matches)

    # ── Metadata analysis ─────────────────────────────────────────────────────
    metadata_result = analyze_metadata(file_content, filename) if file_content else None
    metadata_risk   = metadata_result.metadata_risk_score if metadata_result else 0

    # ── Keyword presence flags ────────────────────────────────────────────────
    financial_detected = _has_any(text_lower, {
        'salary', 'salaire', 'payroll', 'iban', 'financial', 'financier',
        'budget', 'invoice', 'facture',
    })
    hr_detected = _has_any(text_lower, {
        'employee', 'employé', 'hr', 'rh', 'human resources', 'ressources humaines',
        'personnel', 'recruitment', 'recrutement',
    })

    # ── Risk and confidentiality scoring ─────────────────────────────────────
    score_result = compute_scores(
        pii_matches=pii_matches,
        secret_matches=secret_matches,
        text_lower=text_lower,
        metadata_risk_score=metadata_risk,
    )

    # ── GDPR check ────────────────────────────────────────────────────────────
    gdpr_result = check_gdpr(
        text_lower=text_lower,
        pii_count=len(pii_matches),
        secret_count=len(secret_matches),
        pii_matches=pii_matches,
    )

    # ── Recommendations ───────────────────────────────────────────────────────
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

    # ── Persist result ────────────────────────────────────────────────────────
    # ── Classification source (Phase 3 audit fields) ─────────────────────────
    # Derive a human-readable classification source label from the risk/score
    # result so the NOT NULL DB column is always populated.
    classification_source = getattr(score_result, 'classification_source', '') or (
        f'rule:{score_result.confidentiality_level.lower()}'
    )
    classification_rules_matched = getattr(score_result, 'classification_rules_matched', []) or []

    analysis_data = {
        'pii_count':              len(pii_matches),
        'pii_types':              pii_counts,
        'pii_details':            [
            {'type': m.pii_type, 'value': m.value, 'context': m.context}
            for m in pii_matches
        ],
        'secret_count':           len(secret_matches),
        'secret_types':           secret_counts,
        'secret_details':         [
            {'type': m.secret_type, 'value': m.value,
             'confidence': m.confidence, 'context': m.context}
            for m in secret_matches
        ],
        'financial_data_detected':       financial_detected,
        'employee_data_detected':        hr_detected,
        'classification_source':         classification_source,
        'classification_rules_matched':  classification_rules_matched,
        'metadata_risk':           metadata_risk,
        'metadata_details': {
            'author':          metadata_result.author           if metadata_result else None,
            'company':         metadata_result.company          if metadata_result else None,
            'software':        metadata_result.software         if metadata_result else None,
            'created_at':      metadata_result.created_at       if metadata_result else None,
            'modified_at':     metadata_result.modified_at      if metadata_result else None,
            'version':         metadata_result.version          if metadata_result else None,
            'hidden_content':  metadata_result.hidden_text_detected if metadata_result else False,
            'risk_flags':      metadata_result.risk_flags       if metadata_result else [],
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
        'recommendations': [
            {
                'priority':    r.priority,
                'category':    r.category,
                'title':       r.title,
                'description': r.description,
                'action':      r.action,
            }
            for r in rec_list
        ],
        'analysis_version': ANALYSIS_VERSION,
        'analysis_date':    timezone.now(),
    }

    analysis, _ = DocumentSecurityAnalysis.objects.update_or_create(
        document=document,
        defaults=analysis_data,
    )

    logger.info(
        'security_analysis: doc #%s — PII=%d secrets=%d conf=%s risk=%s gdpr=%s',
        document_id,
        len(pii_matches),
        len(secret_matches),
        score_result.confidentiality_level,
        score_result.risk_level,
        gdpr_result.gdpr_status,
    )

    # ── Notify on high-risk documents ─────────────────────────────────────────
    if score_result.risk_level in ('HIGH', 'CRITICAL') or len(secret_matches) > 0:
        _send_security_notification(document, analysis)

    return analysis


def _has_any(text: str, keywords: set) -> bool:
    return any(kw in text for kw in keywords)


def _send_security_notification(document, analysis) -> None:
    """Fire a CRITICAL_RISK notification for high-risk documents."""
    try:
        from notifications.models import create_notification, Notification
        create_notification(
            recipient_username=document.employee_username or 'admin',
            title='⚠ Security Alert: High-Risk Document Detected',
            message=(
                f'Document #{document.id} has been flagged: '
                f'Risk={analysis.risk_level}, '
                f'Confidentiality={analysis.confidentiality_level}. '
                f'{analysis.secret_count} credential(s), '
                f'{analysis.pii_count} PII item(s) detected.'
            ),
            notification_type=Notification.NotificationType.CRITICAL_RISK,
            priority=Notification.Priority.CRITICAL,
            related_object_type='DocumentSecurityAnalysis',
            related_object_id=analysis.id,
        )
    except Exception as exc:
        logger.warning('security_analysis: notification failed: %s', exc)
