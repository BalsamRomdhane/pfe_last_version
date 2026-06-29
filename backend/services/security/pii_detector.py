"""
pii_detector.py — Personally Identifiable Information detection.

Uses compiled regex patterns only — no external ML dependencies.
All patterns follow GDPR Article 4(1) definitions of personal data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

# ── PII pattern registry ──────────────────────────────────────────────────────

@dataclass
class PiiMatch:
    pii_type: str
    value: str          # redacted in production — shown only for audit
    start: int
    end: int
    context: str        # 40-char surrounding context


_PATTERNS: List[tuple[str, re.Pattern]] = [
    # Email
    ('EMAIL',
     re.compile(
         r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b',
         re.IGNORECASE,
     )),
    # French phone — +33, 06, 07, 01-09
    ('PHONE',
     re.compile(
         r'(?:\+33|0033|0)[1-9](?:[\s.\-]?\d{2}){4}\b',
     )),
    # International phone — fallback
    ('PHONE',
     re.compile(
         r'\+\d{1,3}[\s.\-]?\(?\d{1,4}\)?[\s.\-]?\d{1,4}[\s.\-]?\d{1,9}\b',
     )),
    # IBAN
    ('IBAN',
     re.compile(
         r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}(?:[A-Z0-9]{0,16})\b',
         re.IGNORECASE,
     )),
    # Credit / debit card (Luhn not applied — regex only)
    ('CREDIT_CARD',
     re.compile(
         r'\b(?:4[0-9]{12}(?:[0-9]{3})?'         # Visa
         r'|5[1-5][0-9]{14}'                       # MasterCard
         r'|3[47][0-9]{13}'                         # Amex
         r'|6(?:011|5[0-9]{2})[0-9]{12})\b',
     )),
    # French CIN / NIN (15-digit INSEE number)
    ('NATIONAL_ID',
     re.compile(
         r'\b[12][0-9]{2}(?:0[1-9]|1[0-2])[0-9]{5}[0-9]{3}[0-9]{2}\b',
     )),
    # Passport numbers  (generic multi-country format)
    ('PASSPORT',
     re.compile(
         r'\b[A-Z]{1,2}[0-9]{6,9}\b',
         re.IGNORECASE,
     )),
    # Employee / badge number — contextual
    ('EMPLOYEE_ID',
     re.compile(
         r'(?:employee[\s_\-#]*(?:id|number|no\.?|num\.?)|badge[\s_\-#]*(?:id|number|no\.?))'
         r'[\s:]*([A-Z0-9]{4,12})\b',
         re.IGNORECASE,
     )),
    # Date of birth — contextual
    ('DATE_OF_BIRTH',
     re.compile(
         r'(?:date\s+of\s+birth|dob|date\s+de\s+naissance|naissance)'
         r'[\s:]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
         re.IGNORECASE,
     )),
    # Standalone date (dd/mm/yyyy or mm/dd/yyyy) — lower confidence
    ('DATE',
     re.compile(
         r'\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b',
     )),
    # Full name patterns — "Prénom Nom" or "M./Mme Nom Prénom"
    ('FULL_NAME',
     re.compile(
         r'\b(?:M\.|Mme\.?|Mr\.?|Mrs\.?|Dr\.?|Prof\.?)\s+[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜ][a-zàâäéèêëîïôùûü]+(?:\s+[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜ][a-zàâäéèêëîïôùûü]+){0,2}\b',
         re.UNICODE,
     )),
    # Street address — simplified
    ('ADDRESS',
     re.compile(
         r'\b\d{1,5}\s+[A-Za-zÀ-ÿ\s,]{5,50}(?:rue|avenue|boulevard|impasse|allée|chemin|route|street|road|lane|drive|court|place)\b',
         re.IGNORECASE | re.UNICODE,
     )),
]


def detect_pii(text: str) -> List[PiiMatch]:
    """
    Scan ``text`` for PII patterns and return a deduplicated list of matches.

    Overlapping matches for the same character range are deduplicated — the
    most specific type wins.  Sorting is by start position.
    """
    if not text:
        return []

    raw: List[PiiMatch] = []
    for pii_type, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            start, end = m.start(), m.end()
            ctx_start = max(0, start - 20)
            ctx_end   = min(len(text), end + 20)
            context   = text[ctx_start:ctx_end].replace('\n', ' ')
            raw.append(PiiMatch(
                pii_type=pii_type,
                value=_redact(text[start:end]),
                start=start,
                end=end,
                context=context,
            ))

    # Deduplicate: keep longest match per start position
    raw.sort(key=lambda x: (x.start, -(x.end - x.start)))
    seen_ends: set = set()
    deduped: List[PiiMatch] = []
    for match in raw:
        if match.end not in seen_ends:
            deduped.append(match)
            seen_ends.add(match.end)

    return deduped


def count_pii_by_type(matches: List[PiiMatch]) -> dict:
    """Return a dict mapping pii_type → count."""
    counts: dict = {}
    for m in matches:
        counts[m.pii_type] = counts.get(m.pii_type, 0) + 1
    return counts


def _redact(value: str) -> str:
    """Return a redacted version for safe logging (keep first 2 and last 2 chars)."""
    if len(value) <= 4:
        return '****'
    return value[:2] + '*' * (len(value) - 4) + value[-2:]
