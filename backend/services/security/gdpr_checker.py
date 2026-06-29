"""
gdpr_checker.py — GDPR / RGPD compliance assessment.

Evaluates the document text and detection results against key GDPR
requirements without requiring any external services.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class GdprResult:
    has_pii: bool                       = False
    has_sensitive_data: bool            = False
    has_financial_data: bool            = False
    lawful_basis_mentioned: bool        = False
    data_retention_mentioned: bool      = False
    consent_mentioned: bool             = False
    encryption_mentioned: bool          = False
    gdpr_status: str                    = 'UNKNOWN'   # OK / WARNING / NON_COMPLIANT
    compliance_summary: str             = ''
    issues: List[str]                   = field(default_factory=list)
    recommendations: List[str]          = field(default_factory=list)


_LAWFUL_BASIS_KW = {
    'consent', 'consentement', 'legitimate interest', 'intérêt légitime',
    'legal obligation', 'obligation légale', 'vital interest',
    'public task', 'mission de service public',
}
_RETENTION_KW = {
    'retention', 'rétention', 'conservation', 'archivage',
    'deletion', 'suppression', 'purge', 'durée de conservation',
}
_CONSENT_KW = {
    'consent', 'consentement', 'opt-in', 'opt-out',
    'agreement', 'accord',
}
_ENCRYPTION_KW = {
    'encrypt', 'chiffr', 'aes', 'rsa', 'ssl', 'tls', 'https',
    'cipher', 'hash', 'bcrypt',
}
_SENSITIVE_CATEGORIES = {
    # GDPR Article 9 special categories
    'health', 'santé', 'medical', 'médical', 'racial', 'ethnic',
    'political', 'politique', 'religion', 'religious', 'religieux',
    'biometric', 'biométrique', 'genetic', 'génétique',
    'sexual', 'sexuel', 'trade union', 'syndicat',
}
_FINANCIAL_KW = {
    'salary', 'salaire', 'payroll', 'iban', 'credit card', 'carte bancaire',
    'bank account', 'compte bancaire', 'financial', 'financier',
}


def check_gdpr(
    text_lower: str,
    pii_count: int,
    secret_count: int,
    pii_matches: list,
) -> GdprResult:
    """
    Assess GDPR compliance posture from document content.

    Parameters
    ----------
    text_lower   : lower-cased full document text
    pii_count    : total PII items found
    secret_count : total secret items found
    pii_matches  : list of PiiMatch instances

    Returns
    -------
    GdprResult
    """
    result = GdprResult()

    # Presence flags
    result.has_pii              = pii_count > 0
    result.has_sensitive_data   = any(kw in text_lower for kw in _SENSITIVE_CATEGORIES)
    result.has_financial_data   = any(kw in text_lower for kw in _FINANCIAL_KW)
    result.lawful_basis_mentioned  = any(kw in text_lower for kw in _LAWFUL_BASIS_KW)
    result.data_retention_mentioned = any(kw in text_lower for kw in _RETENTION_KW)
    result.consent_mentioned    = any(kw in text_lower for kw in _CONSENT_KW)
    result.encryption_mentioned = any(kw in text_lower for kw in _ENCRYPTION_KW)

    # Issue detection
    if result.has_pii and not result.lawful_basis_mentioned:
        result.issues.append(
            'PII detected but no lawful basis for processing is mentioned (GDPR Art. 6)'
        )
    if result.has_sensitive_data:
        result.issues.append(
            'Special category data (Art. 9) detected — explicit consent or legal basis required'
        )
    if result.has_pii and not result.data_retention_mentioned:
        result.issues.append(
            'PII detected but no data retention/deletion policy mentioned (GDPR Art. 5.1.e)'
        )
    if result.has_financial_data:
        result.issues.append(
            'Financial personal data detected — ensure appropriate access controls'
        )
    if secret_count > 0:
        result.issues.append(
            f'{secret_count} credentials/secrets found in document — immediate remediation required'
        )
    if result.has_pii and not result.encryption_mentioned:
        result.issues.append(
            'PII present without evidence of encryption — consider encrypting at rest/transit (GDPR Art. 32)'
        )

    # Recommendations
    if result.issues:
        result.recommendations.append('Review document for GDPR compliance before sharing.')
    if result.has_pii:
        result.recommendations.append(
            'Anonymise or pseudonymise personal data before distribution.'
        )
    if result.has_sensitive_data:
        result.recommendations.append(
            'Conduct a Data Protection Impact Assessment (DPIA) before processing.'
        )
    if not result.consent_mentioned and result.has_pii:
        result.recommendations.append(
            'Add consent clause or lawful basis statement to the document.'
        )

    # Overall status
    critical_issues = [i for i in result.issues if 'Art.' in i]
    if len(critical_issues) >= 2 or result.has_sensitive_data:
        result.gdpr_status = 'NON_COMPLIANT'
    elif result.issues:
        result.gdpr_status = 'WARNING'
    else:
        result.gdpr_status = 'OK'

    result.compliance_summary = _build_summary(result)
    return result


def _build_summary(r: GdprResult) -> str:
    parts = []
    if r.has_pii:         parts.append('personal data present')
    if r.has_sensitive_data: parts.append('special category data (Art. 9)')
    if r.has_financial_data: parts.append('financial data')
    if not parts:
        return 'No personal data detected — document appears GDPR-safe.'
    return (
        f"Document contains: {', '.join(parts)}. "
        f"GDPR status: {r.gdpr_status}. "
        f"{len(r.issues)} issue(s) identified."
    )
