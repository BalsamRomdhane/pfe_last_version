"""
recommendation_engine.py — Generate actionable security recommendations.

Pure business logic — no DB access.  Input is the aggregated analysis result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Recommendation:
    priority: str       # CRITICAL / HIGH / MEDIUM / LOW
    category: str       # PII / SECRET / METADATA / GDPR / GENERAL
    title: str
    description: str
    action: str


def generate_recommendations(
    pii_count: int,
    pii_types: dict,
    secret_count: int,
    secret_types: dict,
    confidentiality_level: str,
    risk_level: str,
    gdpr_status: str,
    metadata_risk_score: int,
    financial_detected: bool = False,
    hr_detected: bool = False,
    hidden_content: bool = False,
) -> List[Recommendation]:
    """
    Build a prioritised list of security recommendations.

    All parameters come from the upstream detectors — no DB needed.
    """
    recs: List[Recommendation] = []

    # ── Secret / credential recommendations ──────────────────────────────────
    if secret_count > 0:
        recs.append(Recommendation(
            priority='CRITICAL',
            category='SECRET',
            title='Rotate detected credentials immediately',
            description=(
                f'{secret_count} credential(s) or secret(s) were detected in this document. '
                'Exposed credentials must be rotated immediately regardless of whether '
                'the document has been shared.'
            ),
            action='rotate_credentials',
        ))
        recs.append(Recommendation(
            priority='CRITICAL',
            category='SECRET',
            title='Remove secrets from document',
            description='Credentials and secrets must never be stored in documents.',
            action='remove_secrets',
        ))
        if 'JWT' in secret_types or 'BEARER_TOKEN' in secret_types:
            recs.append(Recommendation(
                priority='CRITICAL',
                category='SECRET',
                title='Revoke exposed JWT / Bearer tokens',
                description='JWT or Bearer tokens found — invalidate immediately via the issuing service.',
                action='revoke_tokens',
            ))

    # ── PII recommendations ───────────────────────────────────────────────────
    if pii_count > 0:
        recs.append(Recommendation(
            priority='HIGH',
            category='PII',
            title='Anonymise or pseudonymise personal data',
            description=(
                f'{pii_count} personal data item(s) detected. '
                'Mask or anonymise before sharing outside the organisation.'
            ),
            action='anonymise_pii',
        ))
        if 'IBAN' in pii_types or 'CREDIT_CARD' in pii_types:
            recs.append(Recommendation(
                priority='CRITICAL',
                category='PII',
                title='Remove financial personal data',
                description='IBAN or credit card numbers detected — must be removed or tokenised.',
                action='remove_financial_pii',
            ))
        if 'NATIONAL_ID' in pii_types or 'PASSPORT' in pii_types:
            recs.append(Recommendation(
                priority='HIGH',
                category='PII',
                title='Remove national ID / passport numbers',
                description='Government-issued ID numbers detected — high GDPR risk.',
                action='remove_id_numbers',
            ))

    # ── Metadata recommendations ──────────────────────────────────────────────
    if metadata_risk_score >= 10:
        recs.append(Recommendation(
            priority='MEDIUM',
            category='METADATA',
            title='Strip document metadata before sharing',
            description=(
                'Author name, company, software version or hidden content detected. '
                'Use a metadata stripping tool (e.g. pdf-redact-tools, LibreOffice export).'
            ),
            action='strip_metadata',
        ))
    if hidden_content:
        recs.append(Recommendation(
            priority='HIGH',
            category='METADATA',
            title='Review and remove hidden content / annotations',
            description='Hidden text, tracked changes or annotations detected in the document.',
            action='remove_hidden_content',
        ))

    # ── GDPR recommendations ──────────────────────────────────────────────────
    if gdpr_status == 'NON_COMPLIANT':
        recs.append(Recommendation(
            priority='CRITICAL',
            category='GDPR',
            title='Immediate GDPR compliance review required',
            description=(
                'Document does not meet GDPR requirements. '
                'Do not distribute until compliance issues are resolved.'
            ),
            action='gdpr_compliance_review',
        ))
    elif gdpr_status == 'WARNING':
        recs.append(Recommendation(
            priority='HIGH',
            category='GDPR',
            title='Review GDPR compliance before sharing',
            description='Potential GDPR issues detected — review before distributing externally.',
            action='gdpr_review',
        ))

    # ── Confidentiality / access control ─────────────────────────────────────
    if confidentiality_level in ('RESTRICTED', 'SECRET'):
        recs.append(Recommendation(
            priority='HIGH',
            category='GENERAL',
            title='Restrict document access',
            description=(
                f'Document classified as {confidentiality_level}. '
                'Ensure only authorised personnel can access it.'
            ),
            action='restrict_access',
        ))
        recs.append(Recommendation(
            priority='HIGH',
            category='GENERAL',
            title='Encrypt document at rest and in transit',
            description='High-classification documents must be encrypted.',
            action='encrypt_document',
        ))
    elif confidentiality_level == 'CONFIDENTIAL':
        recs.append(Recommendation(
            priority='MEDIUM',
            category='GENERAL',
            title='Apply access control policy',
            description='Confidential documents should be access-controlled and watermarked.',
            action='apply_access_control',
        ))

    # ── Financial / HR data ───────────────────────────────────────────────────
    if financial_detected:
        recs.append(Recommendation(
            priority='HIGH',
            category='GDPR',
            title='Financial data requires special handling',
            description='Apply GDPR Art. 6(1)(f) or employment contract basis; restrict access.',
            action='financial_data_review',
        ))
    if hr_detected:
        recs.append(Recommendation(
            priority='HIGH',
            category='GDPR',
            title='HR data handling policy required',
            description='Employee data detected — ensure GDPR Art. 88 / employment law compliance.',
            action='hr_data_review',
        ))

    # Remove duplicates by title
    seen = set()
    unique = []
    for r in recs:
        if r.title not in seen:
            seen.add(r.title)
            unique.append(r)

    # Sort by priority
    _order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    unique.sort(key=lambda r: _order.get(r.priority, 9))
    return unique
