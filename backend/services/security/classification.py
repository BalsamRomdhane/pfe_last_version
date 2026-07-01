"""
services/security/classification.py — Document classification engine.

Public API
----------
  ClassificationEngine                  ← pure classification logic (no DB)
    .classify(input)                    → ClassificationResult

  ClassificationService                 ← orchestration (DB read/write)
    .run(document_id)                   → ClassificationResult | None

Classification levels (ascending sensitivity)
----------------------------------------------
  PUBLIC        No sensitive content detected
  INTERNAL      Mild sensitivity (internal keywords, low PII count)
  CONFIDENTIAL  Significant PII, HR/financial data, NDA content
  RESTRICTED    Secrets/credentials found, high PII, explicit labels

Design
------
- The engine is pure Python with no Django imports — testable in isolation.
- Classification uses FIVE independent signals:
    1. PII count and types        (from pii_detector output)
    2. Secret count               (from secret_detector output)
    3. Risk score                 (from risk_scoring output — 0-100)
    4. Sensitive keywords         (configurable per rule)
    5. Explicit classification labels in the document text
- Rules are evaluated in priority order; the highest-priority rule that
  fires wins. If no rule fires, the fallback is PUBLIC.
- `classification_source` records which rule caused the final level.
- `rules_matched` lists every rule that fired (for audit/transparency).
- Configurable via CLASSIFICATION_RULES — no code change needed to tune
  thresholds; settings can be overridden from Django settings in future.

Extensibility (future phases)
------------------------------
  Phase 4 — EncryptionService reads ClassificationResult.level to decide
             whether to encrypt (CONFIDENTIAL / RESTRICTED → encrypt).
  Phase 5 — DocumentStorageService uses level to choose storage tier.
  Phase 8 — AuditService logs classification changes.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, NamedTuple, Optional

logger = logging.getLogger(__name__)


# ── Classification levels ─────────────────────────────────────────────────────

class Level:
    PUBLIC       = 'PUBLIC'
    INTERNAL     = 'INTERNAL'
    CONFIDENTIAL = 'CONFIDENTIAL'
    RESTRICTED   = 'RESTRICTED'

    # Ordered from least to most sensitive (used for max() comparisons)
    ORDER = [PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED]

    @classmethod
    def max(cls, a: str, b: str) -> str:
        """Return the more sensitive of two levels."""
        try:
            return cls.ORDER[max(cls.ORDER.index(a), cls.ORDER.index(b))]
        except ValueError:
            return b


# ── Input / Output types ──────────────────────────────────────────────────────

@dataclass
class ClassificationInput:
    """
    All signals fed into the classification engine.

    All fields come from upstream detectors — caller builds this from the
    results of pii_detector, secret_detector, and risk_scoring.
    """
    pii_count:      int   = 0
    pii_types:      dict  = field(default_factory=dict)   # {type: count}
    secret_count:   int   = 0
    secret_types:   dict  = field(default_factory=dict)
    risk_score:     int   = 0      # 0–100 from risk_scoring.compute_scores()
    text_lower:     str   = ''     # lower-cased full document text
    # Optional: provide a pre-computed confidentiality_level from risk_scoring
    # to use as a baseline (avoids re-scanning keywords already scored there).
    base_level: Optional[str] = None


class ClassificationResult(NamedTuple):
    """Immutable result of a classification run."""
    level:               str        # PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED
    confidence:          float      # 0.0–1.0 — how strongly the evidence supports the level
    source:              str        # name of the winning rule
    rules_matched:       List[str]  # all rules that fired (for audit trail)
    explanation:         str        # one-sentence human-readable explanation


# ── Rule definitions ──────────────────────────────────────────────────────────

@dataclass
class ClassificationRule:
    """A single classification rule evaluated by ClassificationEngine."""
    name:       str         # unique rule identifier (logged, stored)
    level:      str         # level this rule promotes to
    priority:   int         # lower = higher priority (0 is highest)
    description: str        # explanation shown in UI / audit

    def matches(self, inp: ClassificationInput) -> bool:  # pragma: no cover
        raise NotImplementedError


class _ExplicitLabelRule(ClassificationRule):
    """Fires when the document text contains an explicit classification label."""

    # Maps label patterns to levels — checked in priority order
    _LABEL_PATTERNS = [
        (Level.RESTRICTED,   re.compile(
            r'\b(?:restricted|restreint|top\s+secret|highly\s+confidential|hautement\s+confidentiel)\b',
            re.IGNORECASE,
        )),
        (Level.CONFIDENTIAL, re.compile(
            r'\b(?:confidential|confidentiel|company\s+confidential)\b',
            re.IGNORECASE,
        )),
        (Level.INTERNAL,     re.compile(
            r'\b(?:internal|interne|internal\s+use\s+only|usage\s+interne(?:\s+uniquement)?)\b',
            re.IGNORECASE,
        )),
    ]

    def matches(self, inp: ClassificationInput) -> bool:
        for level, pattern in self._LABEL_PATTERNS:
            if pattern.search(inp.text_lower):
                self._matched_level = level
                return True
        return False

    def get_matched_level(self, inp: ClassificationInput) -> str:
        for level, pattern in self._LABEL_PATTERNS:
            if pattern.search(inp.text_lower):
                return level
        return Level.INTERNAL


class _SecretDetectedRule(ClassificationRule):
    """Any credential or secret in the document → RESTRICTED."""

    def matches(self, inp: ClassificationInput) -> bool:
        return inp.secret_count > 0


class _HighPiiRestrictedRule(ClassificationRule):
    """5+ PII items OR high-risk PII types (IBAN, credit card, national ID) → RESTRICTED."""

    _HIGH_RISK_TYPES = {'IBAN', 'CREDIT_CARD', 'NATIONAL_ID', 'PASSPORT'}

    def matches(self, inp: ClassificationInput) -> bool:
        if inp.pii_count >= 5:
            return True
        return bool(inp.pii_types.keys() & self._HIGH_RISK_TYPES)


class _NdaOrLegalRule(ClassificationRule):
    """NDA / legal contract content → CONFIDENTIAL."""

    _PATTERN = re.compile(
        r'\b(?:nda|non[\s\-]?disclosure|accord\s+de\s+confidentialité|'
        r'contrat|contract|legal\s+agreement|accord\s+légal|'
        r'proprietary|propriétaire)\b',
        re.IGNORECASE,
    )

    def matches(self, inp: ClassificationInput) -> bool:
        return bool(self._PATTERN.search(inp.text_lower))


class _FinancialOrHrConfidentialRule(ClassificationRule):
    """Salary / financial / HR data with 1+ PII items → CONFIDENTIAL."""

    _FIN_PATTERN = re.compile(
        r'\b(?:salary|salaire|payroll|paie|budget|invoice|facture|'
        r'financial\s+report|rapport\s+financier|bilan|revenue|profit)\b',
        re.IGNORECASE,
    )
    _HR_PATTERN = re.compile(
        r'\b(?:employee\s+(?:record|file|evaluation|review)|fiche\s+employé|'
        r'performance\s+review|évaluation|onboarding|offboarding|'
        r'hr\s+report|rh\s+rapport|ressources\s+humaines)\b',
        re.IGNORECASE,
    )

    def matches(self, inp: ClassificationInput) -> bool:
        has_fin = bool(self._FIN_PATTERN.search(inp.text_lower))
        has_hr  = bool(self._HR_PATTERN.search(inp.text_lower))
        return (has_fin or has_hr) and inp.pii_count >= 1


class _ModeratePiiRule(ClassificationRule):
    """2–4 PII items → CONFIDENTIAL."""

    def matches(self, inp: ClassificationInput) -> bool:
        return 2 <= inp.pii_count < 5


class _LowPiiOrRiskRule(ClassificationRule):
    """1 PII item OR risk_score 20–49 → INTERNAL."""

    def matches(self, inp: ClassificationInput) -> bool:
        return inp.pii_count == 1 or (20 <= inp.risk_score < 50)


class _HighRiskScoreRule(ClassificationRule):
    """risk_score ≥ 75 → RESTRICTED."""

    def matches(self, inp: ClassificationInput) -> bool:
        return inp.risk_score >= 75


class _MediumRiskScoreRule(ClassificationRule):
    """risk_score 50–74 → CONFIDENTIAL."""

    def matches(self, inp: ClassificationInput) -> bool:
        return 50 <= inp.risk_score < 75


class _InternalKeywordRule(ClassificationRule):
    """Internal-use keywords without higher signals → INTERNAL."""

    _PATTERN = re.compile(
        r'\b(?:draft|brouillon|work\s+in\s+progress|wip|'
        r'preliminary|préliminaire|not\s+for\s+distribution|'
        r'ne\s+pas\s+distribuer|for\s+internal\s+review)\b',
        re.IGNORECASE,
    )

    def matches(self, inp: ClassificationInput) -> bool:
        return bool(self._PATTERN.search(inp.text_lower))


# ── Default rule set ──────────────────────────────────────────────────────────
# Rules are evaluated in ascending priority order (0 = checked first).
# The LAST matching rule wins (highest level takes precedence via Level.max),
# but the explicit-label rule has the final word if it fires.

CLASSIFICATION_RULES: List[ClassificationRule] = [
    # Low-signal rules (checked first — establish baseline)
    _InternalKeywordRule(
        name='internal_keywords',
        level=Level.INTERNAL,
        priority=50,
        description='Internal-use keywords detected (draft, WIP, not for distribution)',
    ),
    _LowPiiOrRiskRule(
        name='low_pii_or_risk',
        level=Level.INTERNAL,
        priority=40,
        description='1 PII item or moderate risk score (20–49)',
    ),

    # Medium-signal rules
    _MediumRiskScoreRule(
        name='medium_risk_score',
        level=Level.CONFIDENTIAL,
        priority=30,
        description='Risk score 50–74 indicates significant sensitivity',
    ),
    _ModeratePiiRule(
        name='moderate_pii',
        level=Level.CONFIDENTIAL,
        priority=30,
        description='2–4 PII items detected',
    ),
    _FinancialOrHrConfidentialRule(
        name='financial_or_hr_with_pii',
        level=Level.CONFIDENTIAL,
        priority=25,
        description='Financial or HR content combined with PII',
    ),
    _NdaOrLegalRule(
        name='nda_or_legal',
        level=Level.CONFIDENTIAL,
        priority=25,
        description='NDA, legal contract, or proprietary content detected',
    ),

    # High-signal rules
    _HighRiskScoreRule(
        name='high_risk_score',
        level=Level.RESTRICTED,
        priority=15,
        description='Risk score ≥ 75 — critical sensitivity',
    ),
    _HighPiiRestrictedRule(
        name='high_pii_or_financial_pii',
        level=Level.RESTRICTED,
        priority=10,
        description='5+ PII items or high-risk PII types (IBAN, credit card, national ID)',
    ),
    _SecretDetectedRule(
        name='secret_detected',
        level=Level.RESTRICTED,
        priority=5,
        description='Credentials or secrets detected — always RESTRICTED',
    ),

    # Explicit label rule — overrides everything when present
    _ExplicitLabelRule(
        name='explicit_classification_label',
        level=Level.CONFIDENTIAL,  # actual level resolved dynamically
        priority=0,
        description='Explicit classification label found in document text',
    ),
]


# ── Classification Engine ─────────────────────────────────────────────────────

class ClassificationEngine:
    """
    Pure classification engine — no Django imports, no DB access.

    Evaluates all rules against a ClassificationInput and returns the
    highest-sensitivity level that any rule supports.

    Usage
    -----
        engine = ClassificationEngine()
        result = engine.classify(ClassificationInput(
            pii_count=3, pii_types={'EMAIL': 2, 'PHONE': 1},
            secret_count=1, risk_score=65, text_lower=doc_text,
        ))
    """

    def __init__(self, rules: Optional[List[ClassificationRule]] = None):
        # Sort by priority (ascending = higher priority rules evaluated last,
        # so higher-level rules can override lower-level ones).
        self._rules = sorted(
            rules or CLASSIFICATION_RULES,
            key=lambda r: r.priority,
            reverse=True,   # highest priority (lowest number) evaluated last → wins
        )

    def classify(self, inp: ClassificationInput) -> ClassificationResult:
        """
        Evaluate all rules and return the final classification.

        Algorithm
        ---------
        1. Start from base level (PUBLIC or inp.base_level).
        2. Evaluate each rule in descending priority.
        3. Accumulate matched rule names.
        4. The final level is the maximum level across all fired rules.
        5. Special case: ExplicitLabelRule resolves its level dynamically.
        """
        current_level  = inp.base_level or Level.PUBLIC
        rules_matched: List[str] = []
        winning_rule   = 'default_public'
        winning_desc   = 'No sensitive content detected.'

        for rule in self._rules:
            if rule.matches(inp):
                rules_matched.append(rule.name)

                # ExplicitLabelRule resolves its level dynamically
                if isinstance(rule, _ExplicitLabelRule):
                    candidate = rule.get_matched_level(inp)
                else:
                    candidate = rule.level

                new_level = Level.max(current_level, candidate)
                if new_level != current_level:
                    current_level = new_level
                    winning_rule  = rule.name
                    winning_desc  = rule.description

        confidence = self._compute_confidence(inp, current_level, rules_matched)

        explanation = self._build_explanation(
            level=current_level,
            rules_matched=rules_matched,
            winning_desc=winning_desc,
            inp=inp,
        )

        return ClassificationResult(
            level=current_level,
            confidence=confidence,
            source=winning_rule,
            rules_matched=rules_matched,
            explanation=explanation,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _compute_confidence(
        inp: ClassificationInput,
        level: str,
        rules_matched: List[str],
    ) -> float:
        """
        Estimate confidence (0.0–1.0) based on the number and type of signals.

        More rules fired + explicit label → higher confidence.
        """
        if not rules_matched:
            return 0.95   # PUBLIC with no signals is highly confident

        base = 0.50
        # Each matched rule adds to confidence
        base += min(len(rules_matched) * 0.10, 0.30)
        # Explicit label is the strongest signal
        if 'explicit_classification_label' in rules_matched:
            base += 0.15
        # Secrets are unambiguous
        if 'secret_detected' in rules_matched:
            base += 0.15
        # High PII count
        if inp.pii_count >= 5:
            base += 0.05

        return round(min(base, 0.99), 2)

    @staticmethod
    def _build_explanation(
        level: str,
        rules_matched: List[str],
        winning_desc: str,
        inp: ClassificationInput,
    ) -> str:
        parts = [f'Classified as {level}']
        if rules_matched:
            parts.append(f'based on: {winning_desc}')
        if inp.pii_count:
            parts.append(f'{inp.pii_count} PII item(s)')
        if inp.secret_count:
            parts.append(f'{inp.secret_count} secret(s)')
        if inp.risk_score:
            parts.append(f'risk score {inp.risk_score}/100')
        return '. '.join(parts) + '.'


# ── Service class ─────────────────────────────────────────────────────────────

class ClassificationService:
    """
    Orchestration class: classifies a document and updates the DB.

    Called by the security pipeline in security/signals.py (Phase 3 stub).
    Also callable directly by views or management commands.

    The classification result is written to DocumentSecurityAnalysis:
      - confidentiality_level      (already exists — overwritten with new value)
      - confidentiality_score      (already exists — overwritten)
      - classification_source      (new field added in migration 0003)
      - classification_rules_matched (new field added in migration 0003)
    """

    _engine = ClassificationEngine()

    @classmethod
    def run(cls, document_id: int) -> ClassificationResult | None:
        """
        Run classification for a document and persist the result.

        Parameters
        ----------
        document_id : int
            PK of the api.Document to classify.

        Returns
        -------
        ClassificationResult on success, None on error.
        """
        from api.models import Document
        from security.models import DocumentSecurityAnalysis

        # ── Load document ─────────────────────────────────────────────────────
        try:
            document = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            logger.error('ClassificationService: Document #%s not found.', document_id)
            return None

        # ── Load existing security analysis (may not exist yet) ───────────────
        try:
            analysis = DocumentSecurityAnalysis.objects.get(document=document)
        except DocumentSecurityAnalysis.DoesNotExist:
            logger.warning(
                'ClassificationService: No SecurityAnalysis for Document #%s — '
                'classification will run with defaults.',
                document_id,
            )
            analysis = None

        # ── Build classification input from analysis data ──────────────────────
        if analysis:
            inp = ClassificationInput(
                pii_count=analysis.pii_count or 0,
                pii_types=analysis.pii_types or {},
                secret_count=analysis.secret_count or 0,
                secret_types=analysis.secret_types or {},
                risk_score=analysis.risk_score or 0,
                text_lower='',   # text not re-extracted here (already scored)
                base_level=None,
            )
        else:
            # No analysis yet — run with document file text if available
            text_lower = cls._extract_text_lower(document)
            # Build a minimal input from raw text scan
            from services.security.pii_detector import detect_pii, count_pii_by_type
            from services.security.secret_detector import detect_secrets, count_secrets_by_type
            pii_matches    = detect_pii(text_lower)
            secret_matches = detect_secrets(text_lower)
            inp = ClassificationInput(
                pii_count=len(pii_matches),
                pii_types=count_pii_by_type(pii_matches),
                secret_count=len(secret_matches),
                secret_types=count_secrets_by_type(secret_matches),
                risk_score=0,
                text_lower=text_lower,
            )

        result = cls._engine.classify(inp)

        # ── Persist result ────────────────────────────────────────────────────
        cls._persist(document_id, result, analysis)

        logger.info(
            'ClassificationService: Document #%s → %s (confidence=%.2f, source=%s)',
            document_id, result.level, result.confidence, result.source,
        )
        return result

    @classmethod
    def _persist(
        cls,
        document_id: int,
        result: ClassificationResult,
        analysis,
    ) -> None:
        """Write classification result to DocumentSecurityAnalysis."""
        from security.models import DocumentSecurityAnalysis

        # Map confidence (0.0–1.0) to a 0–100 score for confidentiality_score
        conf_score = int(result.confidence * 100)

        if analysis is not None:
            DocumentSecurityAnalysis.objects.filter(pk=analysis.pk).update(
                confidentiality_level=result.level,
                confidentiality_score=conf_score,
                classification_source=result.source,
                classification_rules_matched=result.rules_matched,
            )
        else:
            # Create a minimal analysis record with classification data only
            DocumentSecurityAnalysis.objects.update_or_create(
                document_id=document_id,
                defaults={
                    'confidentiality_level':         result.level,
                    'confidentiality_score':         conf_score,
                    'classification_source':         result.source,
                    'classification_rules_matched':  result.rules_matched,
                },
            )

    @staticmethod
    def _extract_text_lower(document) -> str:
        """Extract and lowercase document text. Returns '' on any error."""
        try:
            from api.utils import extract_document_text
            return extract_document_text(document).lower()
        except Exception as exc:
            logger.warning(
                'ClassificationService: text extraction failed for Document #%s — %s',
                document.pk, exc,
            )
            return ''
