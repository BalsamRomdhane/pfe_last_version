import json
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Norme, Rule, Document, Validation, TrainingSample, create_training_sample
from .serializers import (
    NormeSerializer,
    RuleSerializer,
    DocumentSerializer,
    DocumentDetailSerializer,
    ValidationSerializer,
    TrainingSampleSerializer,
)
from authentication.permissions import IsAdmin, IsTeamLead, IsTeamLeadOrAdmin, IsEmployee


def recalculate_document_status(document):
    total_rules = document.norme.rules.count()
    validations = Validation.objects.filter(document=document)
    valid_count = validations.filter(is_valid=True).count()
    invalid_count = validations.filter(is_valid=False).count()
    validated_count = validations.exclude(is_valid__isnull=True).count()

    if total_rules == 0 or validated_count < total_rules:
        new_status = Document.Status.REVIEWING
    elif invalid_count > 0:
        new_status = Document.Status.REJECTED
    else:
        new_status = Document.Status.APPROVED

    if document.status != new_status:
        document.status = new_status
        document.save(update_fields=['status'])
        if new_status in [Document.Status.APPROVED, Document.Status.REJECTED]:
            create_training_sample(document)

    return new_status


class NormeViewSet(viewsets.ModelViewSet):
    queryset = Norme.objects.prefetch_related('rules').all()
    serializer_class = NormeSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save()


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.select_related('norme').prefetch_related('validations').all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsEmployee()]
        if self.action == 'update_status':
            return [IsAuthenticated(), IsTeamLeadOrAdmin()]
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        roles = [str(role).upper() for role in getattr(user, 'roles', []) or []]
        qs = Document.objects.select_related('norme').prefetch_related('validations')

        if 'ADMIN' in roles:
            queryset = qs
        elif 'TEAMLEAD' in roles:
            queryset = qs.filter(employee_department=user.department)
        elif 'EMPLOYEE' in roles:
            queryset = qs.filter(employee_username=user.username)
        else:
            queryset = qs.none()

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DocumentDetailSerializer
        return DocumentSerializer

    def perform_create(self, serializer):
        user = self.request.user
        if 'EMPLOYEE' not in [str(role).upper() for role in getattr(user, 'roles', []) or []]:
            raise PermissionDenied('Only employees can submit documents.')

        serializer.save(
            employee_username=user.username,
            employee_department=getattr(user, 'department', None) or '',
            status=Document.Status.PENDING,
        )

    @action(detail=True, methods=['get'], url_path='rules')
    def rules(self, request, pk=None):
        document = self.get_object()
        rules = document.norme.rules.all()
        serializer = RuleSerializer(rules, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='validations')
    def validations(self, request, pk=None):
        document = self.get_object()
        validations = document.validations.select_related('rule').all()
        serializer = ValidationSerializer(validations, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        document = self.get_object()
        user = request.user
        roles = [str(role).upper() for role in getattr(user, 'roles', []) or []]
        if 'ADMIN' not in roles and 'TEAMLEAD' not in roles:
            raise PermissionDenied('Only team leads or admins can update document status.')

        if 'TEAMLEAD' in roles:
            if document.employee_department and document.employee_department != user.department:
                raise PermissionDenied('Team lead may only update documents for their department.')

        status_value = request.data.get('status')
        if status_value not in [choice[0] for choice in Document.Status.choices]:
            raise ValidationError({'status': 'Invalid status value.'})

        document.status = status_value
        if 'TEAMLEAD' in roles and not document.teamlead_username:
            document.teamlead_username = user.username
        document.save(update_fields=['status', 'teamlead_username'])
        if document.status in [Document.Status.APPROVED, Document.Status.REJECTED]:
            create_training_sample(document)
        return Response({'status': document.status})


class ValidationViewSet(viewsets.ModelViewSet):
    queryset = Validation.objects.select_related('document', 'rule').all()
    serializer_class = ValidationSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'bulk']:
            return [IsAuthenticated(), IsTeamLeadOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        roles = [str(role).upper() for role in getattr(user, 'roles', []) or []]
        if 'ADMIN' in roles:
            return self.queryset
        return self.queryset.filter(document__employee_department=user.department)

    def recalculate_document_status(self, document):
        return recalculate_document_status(document)

    def perform_create(self, serializer):
        validation = serializer.save(teamlead_username=self.request.user.username)
        self.recalculate_document_status(validation.document)

    def perform_update(self, serializer):
        validation = serializer.save()
        self.recalculate_document_status(validation.document)

    def perform_destroy(self, instance):
        document = instance.document
        instance.delete()
        self.recalculate_document_status(document)

    @action(detail=False, methods=['post'], url_path='bulk')
    @transaction.atomic
    def bulk(self, request):
        validations_data = request.data.get('validations')
        if isinstance(validations_data, str):
            try:
                validations_data = json.loads(validations_data)
            except json.JSONDecodeError:
                raise ValidationError({'validations': 'Invalid JSON payload for validations list.'})

        if not isinstance(validations_data, list):
            raise ValidationError({'validations': 'A list of validation items is required.'})

        created_validations = []
        document = None

        for index, item in enumerate(validations_data):
            document_id = item.get('document') or item.get('document_id')
            rule_id = item.get('rule') or item.get('rule_id')
            if not document_id or not rule_id:
                raise ValidationError({'validations': f'Validation item at index {index} must include document and rule ids.'})

            try:
                document = Document.objects.select_related('norme').get(pk=document_id)
            except Document.DoesNotExist:
                raise ValidationError({'document': f'Document id {document_id} does not exist.'})

            try:
                rule = Rule.objects.get(pk=rule_id)
            except Rule.DoesNotExist:
                raise ValidationError({'rule': f'Rule id {rule_id} does not exist.'})

            if rule.norme_id != document.norme_id:
                raise ValidationError({'rule': f'Rule id {rule_id} does not belong to document norme.'})

            is_valid = item.get('is_valid')
            if is_valid is None:
                raise ValidationError({'is_valid': f'Validation item at index {index} must include is_valid.'})

            evidence_text = item.get('evidence_text', '')
            evidence_file = request.FILES.get(f'evidence_file_{index}')

            validation, created = Validation.objects.get_or_create(
                document=document,
                rule=rule,
                defaults={
                    'teamlead_username': request.user.username,
                    'evidence_text': evidence_text,
                    'is_valid': is_valid,
                    **({'evidence_file': evidence_file} if evidence_file is not None else {}),
                },
            )
            if not created:
                validation.teamlead_username = request.user.username
                validation.evidence_text = evidence_text
                validation.is_valid = is_valid
                if evidence_file is not None:
                    validation.evidence_file = evidence_file
                validation.save()

            created_validations.append(validation)

        if document is None:
            raise ValidationError({'validations': 'No valid document found in payload.'})

        self.recalculate_document_status(document)
        document.teamlead_username = request.user.username
        document.save(update_fields=['teamlead_username'])

        serializer = ValidationSerializer(
            Validation.objects.filter(document=document),
            many=True,
            context={'request': request},
        )
        return Response(
            {
                'status': document.status,
                'validations': serializer.data,
                'compliance_score': (
                    Validation.objects.filter(document=document, is_valid=True).count() * 100
                    // max(document.norme.rules.count(), 1)
                ),
            },
            status=status.HTTP_200_OK,
        )


class TrainingSampleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TrainingSample.objects.select_related('document__norme').all()
    serializer_class = TrainingSampleSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        standard = self.request.query_params.get('standard')
        qs = self.queryset

        if standard:
            qs = qs.filter(standard=standard)

        return qs.order_by('-created_at')
