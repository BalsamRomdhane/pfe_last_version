from rest_framework import serializers
from .models import Norme, Rule, Document, Validation, TrainingSample


class RuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rule
        fields = ['id', 'title', 'description']


class NormeSerializer(serializers.ModelSerializer):
    rules = RuleSerializer(many=True)

    class Meta:
        model = Norme
        fields = ['id', 'name', 'description', 'created_at', 'rules']
        read_only_fields = ['created_at']

    def create(self, validated_data):
        rules_data = validated_data.pop('rules', [])
        norme = Norme.objects.create(**validated_data)
        for rule_data in rules_data:
            Rule.objects.create(norme=norme, **rule_data)
        return norme


class DocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField(read_only=True)

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
            'created_at',
        ]
        read_only_fields = ['employee_username', 'employee_department', 'teamlead_username', 'status', 'created_at', 'file_url']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

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
    class Meta:
        model = TrainingSample
        fields = ['id', 'label', 'features', 'standard', 'created_at']
        read_only_fields = ['label', 'features', 'standard', 'created_at']
