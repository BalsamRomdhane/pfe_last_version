"""
secret_detector.py — Detection of secrets, credentials and sensitive tokens.

All patterns use compiled regex only.
No false-positive suppression via allow-lists is applied at this layer;
callers may filter by confidence_score.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass
class SecretMatch:
    secret_type: str
    value: str          # always redacted before storage
    confidence: float   # 0.0 – 1.0
    start: int
    end: int
    context: str


# ── Secret pattern registry ───────────────────────────────────────────────────
# Each entry: (secret_type, pattern, confidence)

_PATTERNS: List[tuple[str, re.Pattern, float]] = [
    # JWT — three base64url segments separated by dots
    ('JWT',
     re.compile(
         r'\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b',
     ), 0.97),

    # Bearer token in header
    ('BEARER_TOKEN',
     re.compile(
         r'\bBearer\s+[A-Za-z0-9_\-\.]+\b',
         re.IGNORECASE,
     ), 0.90),

    # Generic API key patterns (key=value style)
    ('API_KEY',
     re.compile(
         r'(?:api[_\-]?key|apikey|access[_\-]?key|app[_\-]?key)'
         r'\s*[=:]\s*["\']?([A-Za-z0-9_\-]{16,64})["\']?',
         re.IGNORECASE,
     ), 0.85),

    # Password / secret in assignment
    ('PASSWORD',
     re.compile(
         r'(?:password|passwd|pwd|pass|secret|mot[\s_\-]?de[\s_\-]?passe)'
         r'\s*[=:]\s*["\']?(\S{6,64})["\']?',
         re.IGNORECASE,
     ), 0.80),

    # client_secret
    ('CLIENT_SECRET',
     re.compile(
         r'client[_\-]?secret\s*[=:]\s*["\']?([A-Za-z0-9_\-]{8,64})["\']?',
         re.IGNORECASE,
     ), 0.88),

    # Private key header
    ('PRIVATE_KEY',
     re.compile(
         r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----',
     ), 0.99),

    # OpenSSH private key
    ('SSH_PRIVATE_KEY',
     re.compile(
         r'-----BEGIN OPENSSH PRIVATE KEY-----',
     ), 0.99),

    # AWS Access Key ID
    ('AWS_ACCESS_KEY',
     re.compile(
         r'\b(?:AKIA|ASIA|AIDA|AROA|ANPA|ANVA|AIPA)[A-Z0-9]{16}\b',
     ), 0.95),

    # AWS Secret Access Key (contextual)
    ('AWS_SECRET_KEY',
     re.compile(
         r'(?:aws[_\-]?secret|SecretAccessKey)\s*[=:]\s*["\']?([A-Za-z0-9/+=]{40})["\']?',
         re.IGNORECASE,
     ), 0.90),

    # Azure connection string / subscription key
    ('AZURE_KEY',
     re.compile(
         r'(?:AccountKey|SubscriptionKey|azure[_\-]?key)\s*[=:]\s*["\']?([A-Za-z0-9+/=]{20,100})["\']?',
         re.IGNORECASE,
     ), 0.85),

    # OpenAI API key
    ('OPENAI_KEY',
     re.compile(
         r'\bsk-[A-Za-z0-9]{32,50}\b',
     ), 0.96),

    # GitHub personal access token (classic ghp_ prefix)
    ('GITHUB_TOKEN_CLASSIC',
     re.compile(
         r'\bghp_[A-Za-z0-9]{36}\b',
     ), 0.97),

    # GitHub fine-grained PAT (github_pat_ prefix — distinct from classic)
    ('GITHUB_TOKEN_FINEGRAINED',
     re.compile(
         r'\bgithub_pat_[A-Za-z0-9_]{82}\b',
     ), 0.97),

    # Jenkins API token (40-hex characters after known context)
    ('JENKINS_TOKEN',
     re.compile(
         r'(?:jenkins[_\-]?token|JENKINS_TOKEN)\s*[=:]\s*["\']?([a-f0-9]{32,40})["\']?',
         re.IGNORECASE,
     ), 0.85),

    # Google service account / API key
    ('GOOGLE_API_KEY',
     re.compile(
         r'\bAIza[A-Za-z0-9_\-]{35}\b',
     ), 0.95),

    # Database connection string
    ('DB_CONNECTION_STRING',
     re.compile(
         r'(?:postgres|mysql|mongodb|redis|sqlite)://[^\s"\'<>]{8,200}',
         re.IGNORECASE,
     ), 0.88),
]


def detect_secrets(text: str) -> List[SecretMatch]:
    """
    Scan ``text`` for credential and secret patterns.
    Returns a list sorted by confidence (descending), then start position.
    """
    if not text:
        return []

    results: List[SecretMatch] = []
    for secret_type, pattern, confidence in _PATTERNS:
        for m in pattern.finditer(text):
            start, end = m.start(), m.end()
            ctx_start = max(0, start - 20)
            ctx_end   = min(len(text), end + 20)
            context   = text[ctx_start:ctx_end].replace('\n', ' ')
            results.append(SecretMatch(
                secret_type=secret_type,
                value=_redact(text[start:end]),
                confidence=confidence,
                start=start,
                end=end,
                context=context,
            ))

    results.sort(key=lambda x: (-x.confidence, x.start))
    return _deduplicate(results)


def count_secrets_by_type(matches: List[SecretMatch]) -> dict:
    counts: dict = {}
    for m in matches:
        counts[m.secret_type] = counts.get(m.secret_type, 0) + 1
    return counts


def _deduplicate(matches: List[SecretMatch]) -> List[SecretMatch]:
    """Remove overlapping matches, keeping the highest-confidence one."""
    kept: List[SecretMatch] = []
    occupied: List[tuple[int, int]] = []

    for m in matches:
        overlap = any(
            not (m.end <= s or m.start >= e)
            for s, e in occupied
        )
        if not overlap:
            kept.append(m)
            occupied.append((m.start, m.end))

    return kept


def _redact(value: str) -> str:
    if len(value) <= 6:
        return '******'
    return value[:3] + '*' * (len(value) - 6) + value[-3:]
