from django.db import models

from .utils import extract_document_text
from compliance_engine import ComplianceEngine

RULES_BY_STANDARD = {
    'ISO9001': [
        'Identification du document',
        'Version du document',
        'Approbation du document',
        'Lisibilit\u00e9 et format',
        'Contr\u00f4le des modifications',
        'Accessibilit\u00e9',
        'Protection du document',
        'Archivage',
        'Validit\u00e9 du contenu',
        'Signature ou validation officielle',
    ],
    'ISO27001': [],
}


class Norme(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Rule(models.Model):
    class Severity(models.TextChoices):
        CRITICAL = 'CRITICAL', 'Critical'
        HIGH = 'HIGH', 'High'
        MEDIUM = 'MEDIUM', 'Medium'
        LOW = 'LOW', 'Low'
        INFO = 'INFO', 'Informational'

    norme = models.ForeignKey(Norme, on_delete=models.CASCADE, related_name='rules')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=12, choices=Severity.choices, default=Severity.HIGH)
    condition = models.TextField(blank=True)
    action = models.TextField(blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.title


class Document(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        REVIEWING = 'reviewing', 'Under Review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        AUTO_APPROVED = 'auto_approved', 'Auto Approved'

    file = models.FileField(upload_to='documents/%Y/%m/%d/')
    norme = models.ForeignKey(Norme, on_delete=models.PROTECT, related_name='documents')
    employee_username = models.CharField(max_length=150)
    employee_department = models.CharField(max_length=120, blank=True)
    teamlead_username = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    final_decision = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        help_text='Explicit final decision from the team lead.',
    )
    decision_reason = models.TextField(blank=True, default='')
    reviewer_comment = models.TextField(blank=True, default='')
    approved_by = models.CharField(max_length=150, blank=True, default='')
    approved_at = models.DateTimeField(null=True, blank=True)
    review_completed_at = models.DateTimeField(null=True, blank=True)
    is_finalized = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.norme.name} - {self.employee_username}"


class Validation(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='validations')
    rule = models.ForeignKey(Rule, on_delete=models.PROTECT, related_name='validations')
    teamlead_username = models.CharField(max_length=150)
    evidence_text = models.TextField(blank=True)
    evidence_file = models.FileField(upload_to='validations/%Y/%m/%d/', blank=True, null=True)
    is_valid = models.BooleanField(null=True)
    comment = models.TextField(blank=True)
    decision_reason = models.TextField(blank=True, default='')
    reviewer_comment = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['document', 'rule']]
        ordering = ['-updated_at']

    def __str__(self):
        return f"Validation for {self.rule.title} on {self.document}"


class TrainingSample(models.Model):
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='training_sample')
    norm_id = models.PositiveIntegerField(blank=True, null=True)
    rule_id = models.PositiveIntegerField(blank=True, null=True)
    features = models.JSONField(default=dict)
    feature_vector = models.JSONField(default=dict)  # Advanced features for ML
    confidence_score = models.FloatField(default=0.0)
    semantic_score = models.FloatField(default=0.0)  # Semantic similarity score
    teamlead_decision = models.CharField(max_length=50, blank=True)
    final_decision = models.CharField(max_length=20, blank=True, default='pending')
    decision_reason = models.TextField(blank=True, default='')
    approved = models.BooleanField(null=True)
    label = models.CharField(max_length=20)
    standard = models.CharField(max_length=50, default='ISO9001')

    valid_rules_count = models.PositiveIntegerField(default=0)
    invalid_rules_count = models.PositiveIntegerField(default=0)
    total_rules = models.PositiveIntegerField(default=0)
    rule_results_json = models.JSONField(default=dict, blank=True)
    compliance_score = models.FloatField(default=0.0)
    approved_rules = models.JSONField(default=list, blank=True)
    rejected_rules = models.JSONField(default=list, blank=True)
    
    # Text fields for retraining and analysis
    rule_text = models.TextField(blank=True, default='')
    document_text = models.TextField(blank=True, default='')
    evidence_text = models.TextField(blank=True, default='')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Training Dataset'
        verbose_name_plural = 'Training Dataset'
        indexes = [
            models.Index(fields=['standard', '-created_at']),
            models.Index(fields=['norm_id', 'label']),
        ]

    def __str__(self):
        return f"TrainingSample({self.document_id}, {self.label})"


class RuleTrainingSample(models.Model):
    """Per-rule training sample that captures the teamlead reasoning for a single rule on a document.

    This model is intentionally additive and does not replace the existing `TrainingSample`.
    One `RuleTrainingSample` represents one (document, rule) pair and stores evidence,
    reviewer comments and scores.
    """
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='rule_training_samples'
    )
    norm = models.ForeignKey(Norme, on_delete=models.CASCADE)
    rule = models.ForeignKey(Rule, on_delete=models.CASCADE)

    rule_title = models.CharField(max_length=255, blank=True, default='')
    rule_description = models.TextField(blank=True, default='')

    document_text = models.TextField(blank=True, default='')
    evidence_text = models.TextField(blank=True, default='')
    reviewer_comment = models.TextField(blank=True, default='')
    recommendation = models.CharField(max_length=255, blank=True, default='')

    semantic_score = models.FloatField(default=0.0)
    confidence_score = models.FloatField(default=0.0)

    # label: approved / rejected / pending
    label = models.CharField(max_length=32, blank=True, default='')
    final_document_decision = models.CharField(max_length=32, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Rule Training Sample'
        verbose_name_plural = 'Rule Training Samples'
        indexes = [
            models.Index(fields=['norm', 'rule']),
            models.Index(fields=['document', 'rule']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"RuleTrainingSample(doc={self.document_id}, rule={self.rule_id}, label={self.label})"


def extract_features(document):
    """Build one binary feature per ISO rule from team lead validations."""
    standard = document.norme.name if document.norme else None
    if document.norme:
        rules = list(document.norme.rules.order_by('id'))
    else:
        rules = []

    if not rules:
        return {}

    evidence_map = {
        validation.rule_id: 1 if validation.is_valid is True else 0
        for validation in Validation.objects.filter(document=document).select_related('rule')
    }

    features = {}
    for rule in rules:
        features[rule.title] = evidence_map.get(rule.id, 0)

    return features


def build_validation_feature_vector(document):
    """Build an ordered binary feature vector from team lead validations."""
    if not document.norme:
        return []

    rules = list(document.norme.rules.order_by('id'))
    validations = {v.rule_id: v for v in Validation.objects.filter(document=document).select_related('rule')}
    feature_vector = []

    for rule in rules:
        validation = validations.get(rule.id)
        feature_vector.append(1 if validation is not None and validation.is_valid is True else 0)

    return feature_vector


def aggregate_validation_metrics(document):
    """Aggregate classification metrics from team lead validations only.

    The classification dataset uses exactly one binary feature per ISO rule:
    1 means the team lead marked the rule valid, 0 means invalid or not validated.
    """
    validations = list(document.validations.select_related('rule').all())
    rules = list(document.norme.rules.order_by('id')) if document.norme else []
    total_rules = len(rules)

    valid_rules = []
    rejected_rules = []
    rule_results_json = {}
    validation_map = {v.rule_id: v for v in validations if getattr(v, 'rule', None)}

    for rule in rules:
        validation = validation_map.get(rule.id)
        is_valid = 1 if validation is not None and validation.is_valid is True else 0
        rule_results_json[rule.title] = is_valid
        if is_valid:
            valid_rules.append(rule.title)
        else:
            rejected_rules.append(rule.title)

    valid_rules_count = len(valid_rules)
    invalid_rules_count = total_rules - valid_rules_count
    compliance_score = int(round((valid_rules_count / total_rules) * 100)) if total_rules else 0

    return {
        'total_rules': total_rules,
        'valid_rules_count': valid_rules_count,
        'invalid_rules_count': invalid_rules_count,
        'approved_rules': valid_rules,
        'rejected_rules': rejected_rules,
        'rule_results_json': rule_results_json,
        'compliance_score': compliance_score,
    }


def create_training_sample(document, analysis_metrics=None):
    """Create or update a training sample when a document is validated or reviewed."""
    features = extract_features(document)
    feature_vector = build_validation_feature_vector(document)
    standard = document.norme.name if document.norme else 'ISO9001'
    analysis_metrics = analysis_metrics or {}
    metrics = aggregate_validation_metrics(document)

    if not analysis_metrics and document.file:
        try:
            raw_text = extract_document_text(document)
            engine = ComplianceEngine()
            analysis = engine.analyze_document(
                text=raw_text,
                norme=document.norme,
                document=None if getattr(document, 'is_finalized', False) else document,
            )
            analysis_metrics = {
                'confidence_score': float(analysis.get('confidence_score', 0.0)),
                'rule_score': float(analysis.get('rule_score', 0.0)),
                'structure_score': float(analysis.get('structure_score', 0.0)),
                'clarity_score': float(analysis.get('clarity_score', 0.0)),
                'consistency_score': float(analysis.get('consistency_score', 0.0)),
                'similarity_score': float(analysis.get('similarity_score', 0.0)),
                'evidence_score': float(analysis.get('evidence_score', 0.0)),
                'teamlead_decision': analysis.get('decision', ''),
            }
        except Exception:
            analysis_metrics = {}

    status_source = document.final_decision or document.status
    if status_source in [Document.Status.APPROVED, Document.Status.AUTO_APPROVED]:
        approved_flag = True
    elif status_source == Document.Status.REJECTED:
        approved_flag = False
    else:
        approved_flag = None

    teamlead_decision = analysis_metrics.get('teamlead_decision', status_source)
    confidence_score = analysis_metrics.get('confidence_score', 0.0)

    sample, created = TrainingSample.objects.update_or_create(
        document=document,
        defaults={
            'norm_id': document.norme_id,
            'features': features,
            'feature_vector': feature_vector,
            'confidence_score': confidence_score,
            'teamlead_decision': teamlead_decision,
            'final_decision': status_source,
            'decision_reason': document.decision_reason,
            'approved': approved_flag,
            'label': status_source,
            'standard': standard,
            'total_rules': metrics['total_rules'],
            'valid_rules_count': metrics['valid_rules_count'],
            'invalid_rules_count': metrics['invalid_rules_count'],
            'approved_rules': metrics['approved_rules'],
            'rejected_rules': metrics['rejected_rules'],
            'rule_results_json': metrics['rule_results_json'],
            'compliance_score': metrics['compliance_score'],
        },
    )

    if not created:
        updated_fields = []
        if sample.features != features:
            sample.features = features
            updated_fields.append('features')
        if sample.standard != standard:
            sample.standard = standard
            updated_fields.append('standard')
        if sample.label != document.status:
            sample.label = document.status
            updated_fields.append('label')
        if sample.norm_id != document.norme_id:
            sample.norm_id = document.norme_id
            updated_fields.append('norm_id')
        if sample.confidence_score != confidence_score:
            sample.confidence_score = confidence_score
            updated_fields.append('confidence_score')
        if sample.teamlead_decision != teamlead_decision:
            sample.teamlead_decision = teamlead_decision
            updated_fields.append('teamlead_decision')
        if sample.approved != approved_flag:
            sample.approved = approved_flag
            updated_fields.append('approved')
        if sample.feature_vector != feature_vector:
            sample.feature_vector = feature_vector
            updated_fields.append('feature_vector')
        for field in ['total_rules', 'valid_rules_count', 'invalid_rules_count', 'approved_rules', 'rejected_rules', 'rule_results_json', 'compliance_score']:
            if getattr(sample, field) != metrics[field]:
                setattr(sample, field, metrics[field])
                updated_fields.append(field)
        if sample.final_decision != (document.final_decision or document.status):
            sample.final_decision = document.final_decision or document.status
            updated_fields.append('final_decision')
        if sample.decision_reason != document.decision_reason:
            sample.decision_reason = document.decision_reason
            updated_fields.append('decision_reason')
        if updated_fields:
            sample.save(update_fields=updated_fields)

    return sample
