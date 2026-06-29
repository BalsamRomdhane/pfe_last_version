"""security/serializers.py — DRF serializers for DocumentSecurityAnalysis."""
from rest_framework import serializers
from .models import DocumentSecurityAnalysis


class DocumentSecurityAnalysisSerializer(serializers.ModelSerializer):
    is_high_risk = serializers.BooleanField(read_only=True)
    has_secrets  = serializers.BooleanField(read_only=True)

    class Meta:
        model  = DocumentSecurityAnalysis
        fields = [
            'id',
            'document',
            # PII
            'pii_count', 'pii_types', 'pii_details',
            # Secrets
            'secret_count', 'secret_types', 'secret_details',
            # Content flags
            'financial_data_detected', 'employee_data_detected',
            # Metadata
            'metadata_risk', 'metadata_details',
            # Scores
            'confidentiality_level', 'confidentiality_score',
            'risk_score', 'risk_level',
            'score_breakdown', 'score_explanation',
            # GDPR
            'gdpr_status', 'gdpr_has_pii', 'gdpr_has_sensitive',
            'gdpr_has_financial', 'gdpr_issues', 'gdpr_compliance_summary',
            # Recommendations
            'recommendations',
            # Computed
            'is_high_risk', 'has_secrets',
            # Audit
            'analysis_date', 'analysis_version',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class SecurityDashboardStatsSerializer(serializers.Serializer):
    total_analysed         = serializers.IntegerField()
    high_risk_count        = serializers.IntegerField()
    critical_risk_count    = serializers.IntegerField()
    total_pii_detected     = serializers.IntegerField()
    total_secrets_detected = serializers.IntegerField()
    avg_risk_score         = serializers.FloatField()
    avg_confidentiality_score = serializers.FloatField()
    confidentiality_distribution = serializers.DictField()
    risk_distribution            = serializers.DictField()
    gdpr_distribution            = serializers.DictField()
    top_pii_types                = serializers.ListField()
    top_secret_types             = serializers.ListField()
