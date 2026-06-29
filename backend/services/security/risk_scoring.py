"""
risk_scoring.py — Confidentiality and risk score computation.

Scoring is deterministic and explainable — every point is accounted for.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


# ── Level definitions ─────────────────────────────────────────────────────────

CONFIDENTIALITY_LEVELS = {
    (0,  20):  'PUBLIC',
    (20, 40):  'INTERNAL',
    (40, 60):  'CONFIDENTIAL',
    (60, 80):  'RESTRICTED',
    (80, 101): 'SECRET',
}

RISK_LEVELS = {
    (0,  25):  'LOW',
    (25, 50):  'MEDIUM',
    (50, 75):  'HIGH',
    (75, 101): 'CRITICAL',
}


@dataclass
class ScoreResult:
    confidentiality_score: int
    confidentiality_level: str
    risk_score: int
    risk_level: str
    score_breakdown: Dict[str, int]
    explanation: List[str]


# Weights for confidentiality score (total can exceed 100 — clamped)
_CONF_WEIGHTS = {
    'pii_count':           3,    # per PII item (max 30)
    'secret_count':        8,    # per secret (max 40)
    'financial_detected':  15,
    'hr_detected':         10,
    'nda_contract':        20,
    'confidential_keyword':25,
    'restricted_keyword':  35,
    'secret_keyword':      45,
    'metadata_risk':       1,    # per metadata risk point (max 15)
}

# Weights for risk score
_RISK_WEIGHTS = {
    'pii_count':          2,     # per PII (max 20)
    'secret_count':       10,    # per secret (max 40)
    'financial_detected': 15,
    'hr_detected':        10,
    'metadata_risk':      1,     # per metadata point (max 10)
    'sensitive_keywords': 5,
    'high_severity_pii':  8,     # email, IBAN, credit card
}

# Sensitive content keywords
_FINANCIAL_KEYWORDS = {
    'salary', 'salaire', 'payroll', 'paie', 'wage', 'remuneration',
    'rémunération', 'revenue', 'profit', 'budget', 'financial', 'financier',
    'invoice', 'facture', 'balance', 'compte', 'trésorerie',
}

_HR_KEYWORDS = {
    'employee', 'employé', 'hr', 'rh', 'human resources', 'ressources humaines',
    'personnel', 'recruitment', 'recrutement', 'performance review',
    'évaluation', 'onboarding', 'offboarding',
}

_SENSITIVE_LABELS = {
    'confidential', 'confidentiel', 'restricted', 'restreint',
    'secret', 'internal', 'interne', 'internal use only',
    'usage interne', 'nda', 'accord de confidentialité',
    'contract', 'contrat', 'audit report', 'rapport d\'audit',
}

_HIGH_RISK_PII_TYPES = {'EMAIL', 'IBAN', 'CREDIT_CARD', 'NATIONAL_ID', 'PASSPORT'}


def compute_scores(
    pii_matches: list,
    secret_matches: list,
    text_lower: str,
    metadata_risk_score: int,
) -> ScoreResult:
    """
    Compute confidentiality and risk scores from detection results.

    Parameters
    ----------
    pii_matches     : list of PiiMatch
    secret_matches  : list of SecretMatch
    text_lower      : lower-cased document text (for keyword scanning)
    metadata_risk_score : 0–30 from MetadataResult
    """
    pii_count    = len(pii_matches)
    secret_count = len(secret_matches)
    explanation  = []
    breakdown    = {}

    # ── Keyword detection ─────────────────────────────────────────────────────
    financial_detected = any(kw in text_lower for kw in _FINANCIAL_KEYWORDS)
    hr_detected        = any(kw in text_lower for kw in _HR_KEYWORDS)

    nda_contract = any(kw in text_lower for kw in {'nda', 'contrat', 'contract',
                                                    'accord de confidentialité'})
    confidential_kw = any(kw in text_lower for kw in {'confidential', 'confidentiel'})
    restricted_kw   = any(kw in text_lower for kw in {'restricted', 'restreint'})
    secret_kw       = any(kw in text_lower for kw in {'secret'})
    sensitive_kw    = any(kw in text_lower for kw in _SENSITIVE_LABELS)

    high_risk_pii = sum(
        1 for m in pii_matches if m.pii_type in _HIGH_RISK_PII_TYPES
    )

    # ── Confidentiality score ─────────────────────────────────────────────────
    conf_score = 0

    pii_contrib = min(pii_count * _CONF_WEIGHTS['pii_count'], 30)
    if pii_contrib:
        conf_score += pii_contrib
        breakdown['pii'] = pii_contrib
        explanation.append(f'{pii_count} PII item(s) detected (+{pii_contrib} pts)')

    sec_contrib = min(secret_count * _CONF_WEIGHTS['secret_count'], 40)
    if sec_contrib:
        conf_score += sec_contrib
        breakdown['secrets'] = sec_contrib
        explanation.append(f'{secret_count} secret(s)/credential(s) detected (+{sec_contrib} pts)')

    if financial_detected:
        conf_score += _CONF_WEIGHTS['financial_detected']
        breakdown['financial'] = _CONF_WEIGHTS['financial_detected']
        explanation.append('Financial content detected (+15 pts)')

    if hr_detected:
        conf_score += _CONF_WEIGHTS['hr_detected']
        breakdown['hr'] = _CONF_WEIGHTS['hr_detected']
        explanation.append('HR/employee data detected (+10 pts)')

    if secret_kw:
        conf_score += _CONF_WEIGHTS['secret_keyword']
        breakdown['secret_label'] = _CONF_WEIGHTS['secret_keyword']
        explanation.append('Document labeled SECRET (+45 pts)')
    elif restricted_kw:
        conf_score += _CONF_WEIGHTS['restricted_keyword']
        breakdown['restricted_label'] = _CONF_WEIGHTS['restricted_keyword']
        explanation.append('Document labeled RESTRICTED (+35 pts)')
    elif confidential_kw:
        conf_score += _CONF_WEIGHTS['confidential_keyword']
        breakdown['confidential_label'] = _CONF_WEIGHTS['confidential_keyword']
        explanation.append('Document labeled CONFIDENTIAL (+25 pts)')
    elif nda_contract:
        conf_score += _CONF_WEIGHTS['nda_contract']
        breakdown['nda'] = _CONF_WEIGHTS['nda_contract']
        explanation.append('NDA / contract content detected (+20 pts)')

    meta_contrib = min(metadata_risk_score * _CONF_WEIGHTS['metadata_risk'], 15)
    if meta_contrib:
        conf_score += meta_contrib
        breakdown['metadata'] = meta_contrib
        explanation.append(f'Metadata risk score {metadata_risk_score}/30 (+{meta_contrib} pts)')

    conf_score = max(0, min(conf_score, 100))

    # ── Risk score ────────────────────────────────────────────────────────────
    risk_score = 0

    risk_pii = min(pii_count * _RISK_WEIGHTS['pii_count'], 20)
    if risk_pii:
        risk_score += risk_pii

    risk_secret = min(secret_count * _RISK_WEIGHTS['secret_count'], 40)
    if risk_secret:
        risk_score += risk_secret

    if financial_detected:
        risk_score += _RISK_WEIGHTS['financial_detected']
    if hr_detected:
        risk_score += _RISK_WEIGHTS['hr_detected']
    if sensitive_kw:
        risk_score += _RISK_WEIGHTS['sensitive_keywords']

    risk_meta = min(metadata_risk_score * _RISK_WEIGHTS['metadata_risk'], 10)
    risk_score += risk_meta

    risk_high_pii = min(high_risk_pii * _RISK_WEIGHTS['high_severity_pii'], 16)
    risk_score += risk_high_pii

    risk_score = max(0, min(risk_score, 100))

    return ScoreResult(
        confidentiality_score=conf_score,
        confidentiality_level=_level(conf_score, CONFIDENTIALITY_LEVELS),
        risk_score=risk_score,
        risk_level=_level(risk_score, RISK_LEVELS),
        score_breakdown=breakdown,
        explanation=explanation,
    )


def _level(score: int, table: dict) -> str:
    for (low, high), label in table.items():
        if low <= score < high:
            return label
    return list(table.values())[-1]
