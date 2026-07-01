"""
security/models.py — DocumentSecurityAnalysis model.

Stores the complete security analysis result for a document.
All detection results are kept in JSONField columns so the schema
does not need to change when new detectors are added.
"""
from django.db import models
from django.utils import timezone


class DocumentSecurityAnalysis(models.Model):

    # ── Confidentiality levels ────────────────────────────────────────────────
    class ConfidentialityLevel(models.TextChoices):
        PUBLIC       = 'PUBLIC',       'Public'
        INTERNAL     = 'INTERNAL',     'Internal'
        CONFIDENTIAL = 'CONFIDENTIAL', 'Confidential'
        RESTRICTED   = 'RESTRICTED',   'Restricted'
        SECRET       = 'SECRET',       'Secret'

    # ── GDPR status ───────────────────────────────────────────────────────────
    class GdprStatus(models.TextChoices):
        OK            = 'OK',            'Compliant'
        WARNING       = 'WARNING',       'Warning'
        NON_COMPLIANT = 'NON_COMPLIANT', 'Non-Compliant'
        UNKNOWN       = 'UNKNOWN',       'Unknown'

    # ── Risk levels ───────────────────────────────────────────────────────────
    class RiskLevel(models.TextChoices):
        LOW      = 'LOW',      'Low'
        MEDIUM   = 'MEDIUM',   'Medium'
        HIGH     = 'HIGH',     'High'
        CRITICAL = 'CRITICAL', 'Critical'

    # ── Relation ──────────────────────────────────────────────────────────────
    document = models.OneToOneField(
        'api.Document',
        on_delete=models.CASCADE,
        related_name='security_analysis',
    )

    # ── PII ───────────────────────────────────────────────────────────────────
    pii_count   = models.PositiveIntegerField(default=0)
    pii_types   = models.JSONField(default=dict, blank=True,
                                   help_text='{"EMAIL": 2, "PHONE": 1, …}')
    pii_details = models.JSONField(default=list, blank=True,
                                   help_text='List of redacted PII matches with context')

    # ── Secrets ───────────────────────────────────────────────────────────────
    secret_count   = models.PositiveIntegerField(default=0)
    secret_types   = models.JSONField(default=dict, blank=True,
                                      help_text='{"JWT": 1, "AWS_ACCESS_KEY": 1, …}')
    secret_details = models.JSONField(default=list, blank=True,
                                      help_text='List of redacted secret matches')

    # ── Sensitive content flags ───────────────────────────────────────────────
    financial_data_detected = models.BooleanField(default=False)
    employee_data_detected  = models.BooleanField(default=False)

    # ── Metadata ──────────────────────────────────────────────────────────────
    metadata_risk    = models.PositiveSmallIntegerField(default=0,
                                                        help_text='0–30 metadata risk contribution')
    metadata_details = models.JSONField(default=dict, blank=True,
                                        help_text='Extracted document metadata')

    # ── Scores ────────────────────────────────────────────────────────────────
    confidentiality_level = models.CharField(
        max_length=16,
        choices=ConfidentialityLevel.choices,
        default=ConfidentialityLevel.PUBLIC,
    )
    confidentiality_score = models.PositiveSmallIntegerField(default=0,
                                                             help_text='0–100')
    risk_score = models.PositiveSmallIntegerField(default=0,
                                                  help_text='0–100')
    risk_level = models.CharField(
        max_length=8,
        choices=RiskLevel.choices,
        default=RiskLevel.LOW,
    )
    score_breakdown  = models.JSONField(default=dict, blank=True,
                                        help_text='Per-category score contributions')
    score_explanation = models.JSONField(default=list, blank=True,
                                         help_text='Human-readable explanation list')

    # ── GDPR ──────────────────────────────────────────────────────────────────
    gdpr_status           = models.CharField(
        max_length=16,
        choices=GdprStatus.choices,
        default=GdprStatus.UNKNOWN,
    )
    gdpr_has_pii          = models.BooleanField(default=False)
    gdpr_has_sensitive    = models.BooleanField(default=False)
    gdpr_has_financial    = models.BooleanField(default=False)
    gdpr_issues           = models.JSONField(default=list, blank=True)
    gdpr_compliance_summary = models.TextField(blank=True, default='')

    # ── Recommendations ───────────────────────────────────────────────────────
    recommendations = models.JSONField(default=list, blank=True,
                                       help_text='Ordered list of security recommendations')

    # ── Classification audit (Phase 3) ────────────────────────────────────────
    classification_source = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text='Name of the classification rule that determined the final level.',
        verbose_name='Classification source',
    )
    classification_rules_matched = models.JSONField(
        default=list,
        blank=True,
        help_text='List of all classification rule names that fired.',
        verbose_name='Matched classification rules',
    )

    # ── Audit trail ───────────────────────────────────────────────────────────
    analysis_date    = models.DateTimeField(default=timezone.now)
    analysis_version = models.CharField(max_length=20, default='1.0.0')
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-analysis_date']
        verbose_name = 'Document Security Analysis'
        verbose_name_plural = 'Document Security Analyses'
        indexes = [
            models.Index(fields=['risk_level', '-analysis_date']),
            models.Index(fields=['confidentiality_level', '-analysis_date']),
            models.Index(fields=['gdpr_status', '-analysis_date']),
        ]

    def __str__(self):
        return (
            f'SecurityAnalysis(doc={self.document_id}, '
            f'risk={self.risk_level}, '
            f'conf={self.confidentiality_level})'
        )

    @property
    def is_high_risk(self) -> bool:
        return self.risk_level in ('HIGH', 'CRITICAL')

    @property
    def has_secrets(self) -> bool:
        return self.secret_count > 0
