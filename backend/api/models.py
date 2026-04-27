from django.db import models


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
    norme = models.ForeignKey(Norme, on_delete=models.CASCADE, related_name='rules')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

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

    file = models.FileField(upload_to='documents/%Y/%m/%d/')
    norme = models.ForeignKey(Norme, on_delete=models.PROTECT, related_name='documents')
    employee_username = models.CharField(max_length=150)
    employee_department = models.CharField(max_length=120, blank=True)
    teamlead_username = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
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
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['document', 'rule']]
        ordering = ['-updated_at']

    def __str__(self):
        return f"Validation for {self.rule.title} on {self.document}"


class TrainingSample(models.Model):
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='training_sample')
    features = models.JSONField()
    label = models.CharField(max_length=20)
    standard = models.CharField(max_length=50, default='ISO9001')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Training Dataset'
        verbose_name_plural = 'Training Dataset'
        indexes = [
            models.Index(fields=['standard', '-created_at']),
        ]

    def __str__(self):
        return f"TrainingSample({self.document_id}, {self.label})"


def extract_features(document):
    """Build a fixed-order feature mapping from the document's validations."""
    standard = document.norme.name if document.norme else None
    rules = RULES_BY_STANDARD.get(standard, [])

    if not rules:
        return {}

    evidence_map = {
        validation.rule.title: int(bool(validation.is_valid))
        for validation in Validation.objects.filter(document=document).select_related('rule')
    }

    features = {}
    for rule in rules:
        features[rule] = evidence_map.get(rule, 0)

    return features


def create_training_sample(document):
    """Create or update a training sample when a document reaches a final status."""
    if document.status not in [Document.Status.APPROVED, Document.Status.REJECTED]:
        return None

    features = extract_features(document)
    if not features:
        return None

    standard = document.norme.name if document.norme else 'ISO9001'

    sample, created = TrainingSample.objects.get_or_create(
        document=document,
        defaults={
            'features': features,
            'label': document.status,
            'standard': standard,
        },
    )

    if not created and (sample.features != features or sample.label != document.status or sample.standard != standard):
        sample.features = features
        sample.label = document.status
        sample.standard = standard
        sample.save(update_fields=['features', 'label', 'standard'])

    return sample
