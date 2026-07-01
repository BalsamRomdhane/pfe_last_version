from django.db.models.deletion import ProtectedError
from rest_framework import serializers
from .models import (
    Norme,
    Rule,
    Document,
    Validation,
    TrainingSample,
    RuleTrainingSample,
    aggregate_validation_metrics,
)


class RuleSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Rule
        fields = ['id', 'title', 'description', 'severity', 'condition', 'action']


class NormeSerializer(serializers.ModelSerializer):
    rules = RuleSerializer(many=True)

    class Meta:
        model = Norme
        fields = ['id', 'name', 'description', 'created_at', 'rules']
        read_only_fields = ['created_at']

    def create(self, validated_data):
        rules_data = validated_data.pop('rules', [])
        norme_name = validated_data.get('name')

        existing_normes = Norme.objects.filter(name__iexact=norme_name)
        if existing_normes.exists():
            # Keep one norme if present, remove duplicates, then replace its rules
            norme = existing_normes.first()
            duplicates = existing_normes.exclude(id=norme.id)
            try:
                duplicates.delete()
            except ProtectedError:
                # Keep duplicates that are still referenced by documents/validations.
                pass
            norme.description = validated_data.get('description', norme.description)
            norme.save()
            norme.rules.all().delete()
            for rule_data in rules_data:
                rule_data_copy = {k: v for k, v in rule_data.items() if k != 'id'}
                Rule.objects.create(norme=norme, **rule_data_copy)
            return norme

        norme = Norme.objects.create(**validated_data)
        for rule_data in rules_data:
            Rule.objects.create(norme=norme, **rule_data)
        return norme

    def update(self, instance, validated_data):
        rules_data = validated_data.pop('rules', None)
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.save()

        if rules_data is not None:
            existing_rules = {rule.id: rule for rule in instance.rules.all()}
            updated_rule_ids = []

            for rule_data in rules_data:
                rule_id = rule_data.get('id')
                if rule_id is not None:
                    try:
                        rule_id = int(rule_id)
                    except (TypeError, ValueError):
                        rule_id = None

                if rule_id and rule_id in existing_rules:
                    rule = existing_rules[rule_id]
                    rule.title = rule_data.get('title', rule.title)
                    rule.description = rule_data.get('description', rule.description)
                    rule.save()
                    updated_rule_ids.append(rule_id)
                else:
                    rule_data_copy = {k: v for k, v in rule_data.items() if k != 'id'}
                    new_rule = Rule.objects.create(norme=instance, **rule_data_copy)
                    updated_rule_ids.append(new_rule.id)

            # Delete rules that were removed from the update payload
            deletion_errors = []
            for rule_id, rule in existing_rules.items():
                if rule_id not in updated_rule_ids:
                    try:
                        if rule.validations.exists():
                            deletion_errors.append(rule.title or str(rule_id))
                        else:
                            rule.delete()
                    except ProtectedError:
                        deletion_errors.append(rule.title or str(rule_id))

            if deletion_errors:
                raise serializers.ValidationError({
                    'rules': [
                        'Cannot remove rules with existing validations: ' + ', '.join(deletion_errors)
                    ]
                })

        return instance


class DocumentSerializer(serializers.ModelSerializer):
    file_url         = serializers.SerializerMethodField(read_only=True)
    # Phase 2 — lightweight integrity status
    integrity_status = serializers.SerializerMethodField(read_only=True)
    # Phase 6 — authenticated secure view URL (replaces direct file_url access)
    secure_view_url  = serializers.SerializerMethodField(read_only=True)
    # Phase 7 — authenticated secure download URL with watermark
    secure_download_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Document
        fields = [
            'id',
            'norme',
            'file',
            'file_url',
            'employee_username',
            'employee_department',
            'teamlead_username',
            'status',
            'final_decision',
            'decision_reason',
            'reviewer_comment',
            'approved_by',
            'approved_at',
            'review_completed_at',
            'is_finalized',
            'created_at',
            # Phase 2 — integrity (read-only)
            'sha256_hash',
            'hash_algorithm',
            'hash_created_at',
            'integrity_status',
            # Phase 4 — encryption (read-only)
            'encrypted',
            'encrypted_at',
            'encrypted_key_id',
            # Phase 6 — secure view URL (read-only)
            'secure_view_url',
            # Phase 7 — secure download URL (read-only)
            'secure_download_url',
        ]
        read_only_fields = [
            'employee_username', 'employee_department', 'teamlead_username',
            'status', 'created_at', 'file_url',
            'approved_by', 'approved_at', 'review_completed_at', 'is_finalized',
            'sha256_hash', 'hash_algorithm', 'hash_created_at', 'integrity_status',
            'encrypted', 'encrypted_at', 'encrypted_key_id',
            'secure_view_url', 'secure_download_url',
        ]

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_integrity_status(self, obj):
        """
        Return a lightweight integrity status string for the document list view.

        Values
        ------
        'VERIFIED'  — hash present (actual verification happens via /integrity/)
        'PENDING'   — hash not yet computed (pipeline still running)

        Note: full tamper-detection requires calling the /integrity/ endpoint
        which re-hashes the file on demand.  This field only tells the frontend
        whether a hash is on record.
        """
        if obj.sha256_hash:
            return 'VERIFIED'
        return 'PENDING'

    def get_secure_view_url(self, obj):
        """
        Return the authenticated secure-view URL for this document.

        Phase 6: replaces the direct /media/ URL with an endpoint that
        enforces RBAC and transparently decrypts encrypted documents.
        The frontend should use this URL instead of file_url for viewing.
        """
        request = self.context.get('request')
        path = f'/api/security/documents/{obj.pk}/view/'
        if request:
            return request.build_absolute_uri(path)
        return path

    def get_secure_download_url(self, obj):
        """
        Return the authenticated secure-download URL for this document.

        Phase 7: RBAC-protected download with watermark.
        The frontend should use this URL for download buttons.
        """
        request = self.context.get('request')
        path = f'/api/security/documents/{obj.pk}/download/'
        if request:
            return request.build_absolute_uri(path)
        return path

    def create(self, validated_data):
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError('Authentication required to submit a document.')

        if 'EMPLOYEE' not in [str(role).upper() for role in getattr(request.user, 'roles', []) or []]:
            raise serializers.ValidationError('Only employees can submit documents.')

        validated_data['employee_username'] = request.user.username
        validated_data['employee_department'] = getattr(request.user, 'department', '') or ''
        validated_data['status'] = Document.Status.PENDING
        return super().create(validated_data)


class NestedValidationSerializer(serializers.ModelSerializer):
    rule = RuleSerializer(read_only=True)
    evidence_file_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Validation
        fields = [
            'id',
            'rule',
            'evidence_text',
            'evidence_file_url',
            'is_valid',
            'teamlead_username',
            'updated_at',
        ]
        read_only_fields = ['teamlead_username', 'updated_at', 'evidence_file_url']

    def get_evidence_file_url(self, obj):
        request = self.context.get('request')
        if obj.evidence_file and request:
            return request.build_absolute_uri(obj.evidence_file.url)
        return None


class DocumentDetailSerializer(DocumentSerializer):
    norme = NormeSerializer(read_only=True)
    validations = NestedValidationSerializer(many=True, read_only=True)
    compliance_score = serializers.SerializerMethodField(read_only=True)

    class Meta(DocumentSerializer.Meta):
        fields = DocumentSerializer.Meta.fields + ['norme', 'validations', 'compliance_score']

    def get_compliance_score(self, obj):
        total_rules = obj.norme.rules.count()
        if total_rules == 0:
            return 0
        valid_count = sum(1 for validation in obj.validations.all() if validation.is_valid)
        return int((valid_count / total_rules) * 100)


class ValidationSerializer(serializers.ModelSerializer):
    document = serializers.PrimaryKeyRelatedField(queryset=Document.objects.all())
    rule = serializers.PrimaryKeyRelatedField(queryset=Rule.objects.all())
    evidence_file_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Validation
        fields = [
            'id',
            'document',
            'rule',
            'evidence_text',
            'evidence_file',
            'evidence_file_url',
            'is_valid',
            'teamlead_username',
            'updated_at',
        ]
        read_only_fields = ['teamlead_username', 'updated_at', 'evidence_file_url']

    def validate(self, attrs):
        document = attrs.get('document')
        rule = attrs.get('rule')
        if document and rule and rule.norme_id != document.norme_id:
            raise serializers.ValidationError('Rule does not belong to the selected norme.')
        return attrs

    def get_evidence_file_url(self, obj):
        request = self.context.get('request')
        if obj.evidence_file and request:
            return request.build_absolute_uri(obj.evidence_file.url)
        return None

    def create(self, validated_data):
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError('Authentication required to create validation.')

        validated_data['teamlead_username'] = request.user.username
        return Validation.objects.create(**validated_data)

    def update(self, instance, validated_data):
        if 'evidence_file' in validated_data and validated_data['evidence_file'] is None:
            validated_data.pop('evidence_file')
        return super().update(instance, validated_data)


class TrainingSampleSerializer(serializers.ModelSerializer):
    """Serializer for TrainingSample - exposes aggregated validation metrics.
    
    IMPORTANT: total_rules, valid_rules_count, invalid_rules_count, rule_results_json,
    and compliance_score MUST be kept in sync by the signal handler. These are read-only
    and always reflect the database state.
    """
    rules_with_evidence = serializers.SerializerMethodField(read_only=True)
    features_count = serializers.SerializerMethodField(read_only=True)
    rules_count = serializers.SerializerMethodField(read_only=True)
    vector_length = serializers.SerializerMethodField(read_only=True)
    score = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TrainingSample
        fields = [
            'id',
            'document',
            'norm_id',
            'label',
            'features',
            'feature_vector',
            'standard',
            'confidence_score',
            'teamlead_decision',
            'final_decision',
            'decision_reason',
            'approved',
            'created_at',
            'rules_with_evidence',
            'score',
            # DIRECT MODEL FIELDS - always kept synchronized by signal handler
            'total_rules',
            'valid_rules_count',
            'invalid_rules_count',
            'rule_results_json',
            'features_count',
            'rules_count',
            'vector_length',
            'compliance_score',
            'approved_rules',
            'rejected_rules',
        ]
        read_only_fields = [
            'document',
            'norm_id',
            'label',
            'features',
            'standard',
            'confidence_score',
            'teamlead_decision',
            'approved',
            'created_at',
            'rules_with_evidence',
            'score',
            'total_rules',
            'valid_rules_count',
            'invalid_rules_count',
            'rule_results_json',
            'features_count',
            'rules_count',
            'vector_length',
            'compliance_score',
            'approved_rules',
            'rejected_rules',
        ]

    def _feature_values(self, obj):
        if isinstance(obj.features, dict):
            return list(obj.features.values())
        if isinstance(obj.features, list):
            return obj.features
        return []

    def get_rules_count(self, obj):
        if getattr(obj, 'total_rules', None) is not None:
            return obj.total_rules
        if isinstance(obj.features, dict):
            return len(obj.features)
        return 0

    def get_vector_length(self, obj):
        if isinstance(obj.feature_vector, list):
            return len(obj.feature_vector)
        if isinstance(obj.feature_vector, dict):
            feature_list = obj.feature_vector.get('feature_list') if isinstance(obj.feature_vector.get('feature_list'), list) else None
            if feature_list is not None:
                return len(feature_list)
            return len(obj.feature_vector)
        return 0

    def get_score(self, obj):
        if getattr(obj, 'compliance_score', None) is not None:
            return float(obj.compliance_score or 0.0)
        if getattr(obj, 'confidence_score', None) is not None:
            return float(obj.confidence_score or 0.0) * 100.0
        return 0.0

    def _validation_metrics(self, obj):
        """
        DEPRECATED: Kept for backwards compatibility in get_rules_with_evidence().
        
        All other metrics should be read directly from model fields, which are
        kept synchronized by the signal handler.
        """
        if obj.document_id and getattr(obj, 'document', None):
            return aggregate_validation_metrics(obj.document)
        return {
            'total_rules': obj.total_rules,
            'valid_rules_count': obj.valid_rules_count,
            'invalid_rules_count': obj.invalid_rules_count,
            'rule_results_json': obj.rule_results_json or {},
            'compliance_score': obj.compliance_score,
        }

    def get_rules_with_evidence(self, obj):
        if not obj.document:
            return []

        validations = {
            validation.rule.title: validation
            for validation in obj.document.validations.select_related('rule').all()
        }

        evidence_rows = []
        metrics = self._validation_metrics(obj)
        rule_results = metrics.get('rule_results_json') or {}
        if isinstance(rule_results, dict) and rule_results:
            for rule_name, feature_value in rule_results.items():
                validation = validations.get(rule_name)
                evidence_rows.append({
                    'rule': rule_name,
                    'feature_value': int(feature_value or 0),
                    'evidence': validation.evidence_text if validation else '',
                })
        elif isinstance(rule_results, list):
            for rule_item in rule_results:
                rule_name = rule_item.get('rule_title') or rule_item.get('rule') or ''
                validation = validations.get(rule_name)
                evidence_rows.append({
                    'rule': rule_name,
                    'feature_value': bool(rule_item.get('is_valid')),
                    'evidence': rule_item.get('evidence_text') or rule_item.get('evidence') or (validation.evidence_text if validation else ''),
                })
        elif isinstance(obj.features, dict):
            for rule_name, feature_value in obj.features.items():
                validation = validations.get(rule_name)
                evidence_rows.append({
                    'rule': rule_name,
                    'feature_value': bool(feature_value),
                    'evidence': validation.evidence_text if validation else '',
                })
        else:
            for validation in obj.document.validations.select_related('rule').all():
                evidence_rows.append({
                    'rule': validation.rule.title,
                    'feature_value': validation.is_valid,
                    'evidence': validation.evidence_text or '',
                })

        return evidence_rows

    def get_features_count(self, obj):
        if isinstance(obj.feature_vector, list):
            return len(obj.feature_vector)
        if isinstance(obj.features, dict):
            return len(obj.features)
        return 0


class RuleTrainingSampleSerializer(serializers.ModelSerializer):
    rule = serializers.SerializerMethodField(read_only=True)
    evidence = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = RuleTrainingSample
        fields = [
            'id',
            'document',
            'norm',
            'rule',
            'rule_title',
            'rule_description',
            'evidence_text',
            'evidence',
            'reviewer_comment',
            'recommendation',
            'label',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_rule(self, obj):
        return obj.rule.title if obj.rule else None

    def get_evidence(self, obj):
        return obj.evidence_text or ''

