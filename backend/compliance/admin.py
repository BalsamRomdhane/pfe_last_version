from django.contrib import admin
from .models import AuditLog, Risk, PeriodicReview, CriticalControl, ComplianceCoverage, AuditReadiness, ComplianceMaturity, EvidenceQualityScore

admin.site.register(AuditLog)
admin.site.register(Risk)
admin.site.register(PeriodicReview)
admin.site.register(CriticalControl)
admin.site.register(ComplianceCoverage)
admin.site.register(AuditReadiness)
admin.site.register(ComplianceMaturity)
admin.site.register(EvidenceQualityScore)
