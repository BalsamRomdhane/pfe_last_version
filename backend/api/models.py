from django.db import models


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
