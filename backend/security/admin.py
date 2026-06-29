"""security/admin.py — Django admin registration for DocumentSecurityAnalysis."""
from django.contrib import admin

from .models import DocumentSecurityAnalysis


@admin.register(DocumentSecurityAnalysis)
class DocumentSecurityAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'document',
        'confidentiality_level',
        'confidentiality_score',
        'risk_level',
        'risk_score',
        'pii_count',
        'secret_count',
        'gdpr_status',
        'analysis_date',
        'analysis_version',
    )
    list_filter = (
        'confidentiality_level',
        'risk_level',
        'gdpr_status',
        'financial_data_detected',
        'employee_data_detected',
        'analysis_version',
    )
    search_fields = ('document__title', 'document__employee_username')
    readonly_fields = (
        'document',
        'pii_count', 'pii_types', 'pii_details',
        'secret_count', 'secret_types', 'secret_details',
        'financial_data_detected', 'employee_data_detected',
        'metadata_risk', 'metadata_details',
        'confidentiality_level', 'confidentiality_score',
        'risk_score', 'risk_level',
        'score_breakdown', 'score_explanation',
        'gdpr_status', 'gdpr_has_pii', 'gdpr_has_sensitive',
        'gdpr_has_financial', 'gdpr_issues', 'gdpr_compliance_summary',
        'recommendations',
        'analysis_date', 'analysis_version',
        'created_at', 'updated_at',
    )
    ordering = ('-analysis_date',)
    date_hierarchy = 'analysis_date'

    def has_add_permission(self, request):
        # Analyses are created programmatically only
        return False
