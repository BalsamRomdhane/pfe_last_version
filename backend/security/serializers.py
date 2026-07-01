"""
security/serializers.py — DRF serializers for the Document Security app.

Serializers defined here
------------------------
  DocumentSecurityAnalysisSerializer   existing — full analysis result
  SecurityDashboardStatsSerializer     existing — dashboard KPIs
  DocumentIntegritySerializer          NEW (Phase 2) — integrity check response
"""
from rest_framework import serializers
from .models import DocumentSecurityAnalysis


class DocumentSecurityAnalysisSerializer(serializers.ModelSerializer):
    is_high_risk    = serializers.BooleanField(read_only=True)
    has_secrets     = serializers.BooleanField(read_only=True)
    # Phase 6 — secure view URL
    secure_view_url     = serializers.SerializerMethodField(read_only=True)
    # Phase 7 — secure download URL
    secure_download_url = serializers.SerializerMethodField(read_only=True)

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
            # Phase 3 — Classification audit
            'classification_source',
            'classification_rules_matched',
            # Phase 6 — Secure view
            'secure_view_url',
            # Phase 7 — Secure download
            'secure_download_url',
            # Computed
            'is_high_risk', 'has_secrets',
            # Audit
            'analysis_date', 'analysis_version',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_secure_view_url(self, obj):
        request = self.context.get('request')
        if request is None:
            return f'/api/security/documents/{obj.document_id}/view/'
        return request.build_absolute_uri(
            f'/api/security/documents/{obj.document_id}/view/'
        )

    def get_secure_download_url(self, obj):
        request = self.context.get('request')
        if request is None:
            return f'/api/security/documents/{obj.document_id}/download/'
        return request.build_absolute_uri(
            f'/api/security/documents/{obj.document_id}/download/'
        )


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


# ── Phase 2 — Integrity verification serializer ───────────────────────────────

class DocumentIntegritySerializer(serializers.Serializer):
    """
    Response shape for GET /api/security/documents/<id>/integrity/

    Fields
    ------
    document_id     PK of the document checked.
    is_valid        True if the file on disk matches the stored SHA-256 hash.
    status          Human-friendly status string: 'VERIFIED', 'TAMPERED',
                    'PENDING', 'FILE_MISSING', or 'NOT_FOUND'.
    stored_hash     The SHA-256 digest recorded at upload time (64 hex chars).
    computed_hash   The SHA-256 digest of the current file (64 hex chars),
                    empty string if the file could not be read.
    hash_algorithm  Algorithm used, always 'sha256'.
    hash_created_at ISO-8601 timestamp when the hash was last computed, or null.
    reason          One-sentence explanation suitable for display in the UI.
    """
    document_id     = serializers.IntegerField()
    is_valid        = serializers.BooleanField()
    status          = serializers.CharField()
    stored_hash     = serializers.CharField(allow_blank=True)
    computed_hash   = serializers.CharField(allow_blank=True)
    hash_algorithm  = serializers.CharField(allow_blank=True)
    hash_created_at = serializers.DateTimeField(allow_null=True)
    reason          = serializers.CharField()
