"""
Compliance OS Models.
All designed for ISO 27001 / TISAX / SOC2 / NIS2 / PCI-DSS / GDPR.
"""
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE        = 'CREATE',        'Create'
        UPDATE        = 'UPDATE',        'Update'
        DELETE        = 'DELETE',        'Delete'
        SOFT_DELETE   = 'SOFT_DELETE',   'Soft Delete'
        VALIDATE      = 'VALIDATE',      'Validate'
        APPROVE       = 'APPROVE',       'Approve'
        REJECT        = 'REJECT',        'Reject'
        STATUS_CHANGE = 'STATUS_CHANGE', 'Status Change'
        VERSION_CREATE= 'VERSION_CREATE','Version Create'
        RESTORE       = 'RESTORE',       'Restore'
        REVIEW        = 'REVIEW',        'Review'
        RISK_ACCEPT   = 'RISK_ACCEPT',   'Risk Accept'
        RISK_MITIGATE = 'RISK_MITIGATE', 'Risk Mitigate'
        EXPORT        = 'EXPORT',        'Export'
        # ── Phase 8 — Document security actions ──────────────────────────────
        VIEW              = 'VIEW',              'Document Viewed'
        DOWNLOAD          = 'DOWNLOAD',          'Document Downloaded'
        DECRYPT           = 'DECRYPT',           'Document Decrypted'
        INTEGRITY_CHECK   = 'INTEGRITY_CHECK',   'Integrity Check'
        ENCRYPT           = 'ENCRYPT',           'Document Encrypted'
        SECURITY_ANALYSIS = 'SECURITY_ANALYSIS', 'Security Analysis'

    entity_type  = models.CharField(max_length=100)
    entity_id    = models.CharField(max_length=64)
    action       = models.CharField(max_length=32, choices=Action.choices)
    old_value    = models.JSONField(null=True, blank=True)
    new_value    = models.JSONField(null=True, blank=True)
    performed_by = models.CharField(max_length=150)
    performed_at = models.DateTimeField(auto_now_add=True)
    reason       = models.TextField(blank=True, default='')
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    user_agent   = models.CharField(max_length=512, blank=True, default='')
    session_id   = models.CharField(max_length=128, blank=True, default='')
    extra        = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-performed_at']
        verbose_name = 'Audit Log'
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['performed_by', '-performed_at']),
            models.Index(fields=['action', '-performed_at']),
        ]

    def __str__(self):
        return f"[{self.action}] {self.entity_type}/{self.entity_id} by {self.performed_by}"


class DocumentVersion(models.Model):
    document       = models.ForeignKey('api.Document', on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField(default=1)
    parent_version = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    is_current     = models.BooleanField(default=True)
    snapshot       = models.JSONField(default=dict)
    changed_by     = models.CharField(max_length=150)
    change_reason  = models.TextField(blank=True, default='')
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version_number']
        unique_together = [['document', 'version_number']]

    def __str__(self):
        return f"Doc#{self.document_id} v{self.version_number}"


class EvidenceVersion(models.Model):
    evidence       = models.ForeignKey('api.RuleTrainingSample', on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField(default=1)
    parent_version = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    is_current     = models.BooleanField(default=True)
    snapshot       = models.JSONField(default=dict)
    changed_by     = models.CharField(max_length=150)
    change_reason  = models.TextField(blank=True, default='')
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version_number']
        unique_together = [['evidence', 'version_number']]

    def __str__(self):
        return f"Evidence#{self.evidence_id} v{self.version_number}"


class EvidenceQualityScore(models.Model):
    class Level(models.TextChoices):
        EXCELLENT = 'EXCELLENT', 'Excellent (90-100)'
        GOOD      = 'GOOD',      'Good (70-89)'
        WARNING   = 'WARNING',   'Warning (50-69)'
        POOR      = 'POOR',      'Poor (0-49)'

    evidence        = models.OneToOneField('api.RuleTrainingSample', on_delete=models.CASCADE, related_name='quality_score')
    quality_score   = models.FloatField(default=0.0)
    quality_level   = models.CharField(max_length=16, choices=Level.choices, default=Level.POOR)
    has_evidence_text = models.BooleanField(default=False)
    has_document    = models.BooleanField(default=False)
    has_human_review= models.BooleanField(default=False)
    is_not_duplicate= models.BooleanField(default=True)
    has_recent_review= models.BooleanField(default=False)
    has_comment     = models.BooleanField(default=False)
    computed_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Evidence Quality Score'

    @classmethod
    def compute(cls, evidence):
        score = 0
        has_evidence_text = bool((evidence.evidence_text or '').strip())
        has_document      = evidence.document_id is not None
        has_human_review  = evidence.label in ('approved', 'rejected')
        has_comment       = bool((evidence.reviewer_comment or '').strip())
        from django.utils import timezone as tz
        from datetime import timedelta
        has_recent_review = (
            evidence.updated_at >= tz.now() - timedelta(days=90)
            if hasattr(evidence, 'updated_at') and evidence.updated_at else False
        )
        is_not_duplicate = not (
            evidence.evidence_text and
            evidence.__class__.objects.filter(
                norm=evidence.norm, evidence_text=evidence.evidence_text
            ).exclude(pk=evidence.pk).exists()
        )
        if has_evidence_text: score += 20
        if has_document:      score += 20
        if has_human_review:  score += 20
        if is_not_duplicate:  score += 20
        if has_recent_review: score += 10
        if has_comment:       score += 10
        level = (cls.Level.EXCELLENT if score >= 90 else cls.Level.GOOD if score >= 70
                 else cls.Level.WARNING if score >= 50 else cls.Level.POOR)
        obj, _ = cls.objects.update_or_create(
            evidence=evidence,
            defaults={
                'quality_score': float(score), 'quality_level': level,
                'has_evidence_text': has_evidence_text, 'has_document': has_document,
                'has_human_review': has_human_review, 'is_not_duplicate': is_not_duplicate,
                'has_recent_review': has_recent_review, 'has_comment': has_comment,
            }
        )
        return obj

    def __str__(self):
        return f"Quality[{self.quality_level}={self.quality_score}] evidence#{self.evidence_id}"


class ComplianceCoverage(models.Model):
    norme            = models.OneToOneField('api.Norme', on_delete=models.CASCADE, related_name='coverage')
    total_rules      = models.PositiveIntegerField(default=0)
    covered_rules    = models.PositiveIntegerField(default=0)
    critical_rules   = models.PositiveIntegerField(default=0)
    critical_covered = models.PositiveIntegerField(default=0)
    coverage_pct     = models.FloatField(default=0.0)
    critical_pct     = models.FloatField(default=0.0)
    uncovered_rules  = models.JSONField(default=list, blank=True)
    computed_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Compliance Coverage'

    def __str__(self):
        return f"{self.norme.name}: {self.coverage_pct:.1f}%"


class AuditReadiness(models.Model):
    class Status(models.TextChoices):
        READY     = 'READY',     'Audit Ready'
        PARTIAL   = 'PARTIAL',   'Partially Ready'
        NOT_READY = 'NOT_READY', 'Not Ready'

    norme              = models.OneToOneField('api.Norme', on_delete=models.CASCADE, related_name='audit_readiness')
    score              = models.FloatField(default=0.0)
    status             = models.CharField(max_length=16, choices=Status.choices, default=Status.NOT_READY)
    coverage_ok        = models.BooleanField(default=False)
    quality_ok         = models.BooleanField(default=False)
    no_expired         = models.BooleanField(default=False)
    no_critical_gaps   = models.BooleanField(default=False)
    low_duplication    = models.BooleanField(default=False)
    avg_quality_score  = models.FloatField(default=0.0)
    duplication_rate   = models.FloatField(default=0.0)
    expired_count      = models.PositiveIntegerField(default=0)
    critical_gap_count = models.PositiveIntegerField(default=0)
    computed_at        = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Audit Readiness'

    def __str__(self):
        return f"{self.norme.name}: {self.status} ({self.score:.0f}/100)"


class Risk(models.Model):
    class Severity(models.TextChoices):
        LOW      = 'LOW',      'Low'
        MEDIUM   = 'MEDIUM',   'Medium'
        HIGH     = 'HIGH',     'High'
        CRITICAL = 'CRITICAL', 'Critical'

    class Status(models.TextChoices):
        OPEN      = 'OPEN',      'Open'
        MITIGATED = 'MITIGATED', 'Mitigated'
        ACCEPTED  = 'ACCEPTED',  'Accepted'
        CLOSED    = 'CLOSED',    'Closed'

    standard        = models.ForeignKey('api.Norme', on_delete=models.CASCADE, related_name='risks')
    rule            = models.ForeignKey('api.Rule', on_delete=models.CASCADE, related_name='risks', null=True, blank=True)
    title           = models.CharField(max_length=255)
    description     = models.TextField(blank=True)
    severity        = models.CharField(max_length=12, choices=Severity.choices, default=Severity.MEDIUM)
    likelihood      = models.PositiveSmallIntegerField(default=3)
    impact          = models.PositiveSmallIntegerField(default=3)
    risk_score      = models.FloatField(default=9.0)
    owner           = models.CharField(max_length=150, blank=True)
    mitigation_plan = models.TextField(blank=True)
    status          = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    due_date        = models.DateField(null=True, blank=True)
    created_by      = models.CharField(max_length=150, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-risk_score', '-created_at']
        indexes = [
            models.Index(fields=['standard', 'status']),
            models.Index(fields=['-risk_score']),
        ]

    def save(self, *args, **kwargs):
        self.risk_score = self.likelihood * self.impact
        if self.risk_score >= 20:   self.severity = self.Severity.CRITICAL
        elif self.risk_score >= 12: self.severity = self.Severity.HIGH
        elif self.risk_score >= 6:  self.severity = self.Severity.MEDIUM
        else:                       self.severity = self.Severity.LOW
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.severity}] {self.title}"


class PeriodicReview(models.Model):
    class Frequency(models.TextChoices):
        MONTHLY   = 'MONTHLY',   'Monthly'
        QUARTERLY = 'QUARTERLY', 'Quarterly'
        BIANNUAL  = 'BIANNUAL',  'Bi-annual'
        ANNUAL    = 'ANNUAL',    'Annual'

    class ReviewStatus(models.TextChoices):
        CURRENT      = 'CURRENT',      'Current'
        NEEDS_REVIEW = 'NEEDS_REVIEW',  'Needs Review'
        OVERDUE      = 'OVERDUE',       'Overdue'

    rule             = models.OneToOneField('api.Rule', on_delete=models.CASCADE, related_name='review_schedule')
    review_frequency = models.CharField(max_length=16, choices=Frequency.choices, default=Frequency.ANNUAL)
    last_review_date = models.DateField(null=True, blank=True)
    next_review_date = models.DateField(null=True, blank=True)
    review_status    = models.CharField(max_length=16, choices=ReviewStatus.choices, default=ReviewStatus.CURRENT)
    reviewed_by      = models.CharField(max_length=150, blank=True)
    review_notes     = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Periodic Review'

    def update_status(self):
        from datetime import date
        today = date.today()
        if not self.next_review_date:
            self.review_status = self.ReviewStatus.CURRENT
        elif self.next_review_date < today:
            self.review_status = self.ReviewStatus.OVERDUE
        elif (self.next_review_date - today).days <= 30:
            self.review_status = self.ReviewStatus.NEEDS_REVIEW
        else:
            self.review_status = self.ReviewStatus.CURRENT

    def __str__(self):
        return f"Review({self.rule.title}): {self.review_status}"


class CriticalControl(models.Model):
    rule        = models.OneToOneField('api.Rule', on_delete=models.CASCADE, related_name='critical_control')
    is_critical = models.BooleanField(default=True)
    rationale   = models.TextField(blank=True)
    frameworks  = models.JSONField(default=list, blank=True)
    control_id  = models.CharField(max_length=64, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Critical Control'

    def __str__(self):
        return f"{'[CRITICAL]' if self.is_critical else '[Normal]'} {self.rule.title}"


class ComplianceMaturity(models.Model):
    class Level(models.TextChoices):
        INITIAL    = 'INITIAL',    'Initial (0-40)'
        DEVELOPING = 'DEVELOPING', 'Developing (41-60)'
        MANAGED    = 'MANAGED',    'Managed (61-80)'
        OPTIMIZED  = 'OPTIMIZED',  'Optimized (81-100)'

    norme           = models.OneToOneField('api.Norme', on_delete=models.CASCADE, related_name='maturity')
    maturity_score  = models.FloatField(default=0.0)
    maturity_level  = models.CharField(max_length=16, choices=Level.choices, default=Level.INITIAL)
    coverage_score  = models.FloatField(default=0.0)
    quality_score   = models.FloatField(default=0.0)
    readiness_score = models.FloatField(default=0.0)
    risk_score      = models.FloatField(default=0.0)
    computed_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Compliance Maturity'

    def __str__(self):
        return f"{self.norme.name}: {self.maturity_level} ({self.maturity_score:.0f}/100)"
