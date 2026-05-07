import json
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.views import APIView

from .models import Norme, Rule, Document, Validation, TrainingSample, create_training_sample
from .serializers import (
    NormeSerializer,
    RuleSerializer,
    DocumentSerializer,
    DocumentDetailSerializer,
    ValidationSerializer,
    TrainingSampleSerializer,
)
from .utils import extract_text, extract_features, compute_score
from authentication.permissions import IsAdmin, IsTeamLead, IsTeamLeadOrAdmin, IsEmployee
from ml.search import SemanticSearchEngine
from ml.train import train_model
from ml.train_models import train_all_models, load_trained_model, build_feature_vector


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


class ExtractFeaturesView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        document_file = request.FILES.get('file')
        standard = request.data.get('standard')

        if not document_file:
            raise ValidationError({'file': 'This field is required.'})
        if not standard:
            raise ValidationError({'standard': 'This field is required.'})

        text = extract_text(document_file)
        features = extract_features(text, standard)
        compliance, valid_rules, invalid_rules = compute_score(features)

        return Response({
            'standard': standard,
            'features': features,
            'valid_rules': valid_rules,
            'invalid_rules': invalid_rules,
            'compliance': compliance,
        })


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

        # If no validations exist and we're setting a final status, create default validations
        if not document.validations.exists() and status_value in [Document.Status.APPROVED, Document.Status.REJECTED]:
            self._create_default_validations(document, status_value, user.username)

        document.status = status_value
        if 'TEAMLEAD' in roles and not document.teamlead_username:
            document.teamlead_username = user.username
        document.save(update_fields=['status', 'teamlead_username'])
        if document.status in [Document.Status.APPROVED, Document.Status.REJECTED]:
            create_training_sample(document)
        return Response({'status': document.status})

    def _create_default_validations(self, document, status_value, teamlead_username):
        """Create default validations for all rules when document is validated directly."""
        from .models import RULES_BY_STANDARD
        
        rules = document.norme.rules.all()
        standard = document.norme.name
        rule_titles = RULES_BY_STANDARD.get(standard, [])
        
        # Determine default validation based on final status
        is_valid_default = (status_value == Document.Status.APPROVED)
        
        # Create evidence text based on status
        if is_valid_default:
            evidence_text = "Document validé directement par le teamlead - toutes les règles conformes."
        else:
            evidence_text = "Document rejeté directement par le teamlead - non-conformité détectée."
        
        for rule in rules:
            Validation.objects.get_or_create(
                document=document,
                rule=rule,
                defaults={
                    'teamlead_username': teamlead_username,
                    'evidence_text': evidence_text,
                    'is_valid': is_valid_default,
                }
            )


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


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def train_model_api(request):
    standard = request.data.get('standard')
    result = train_model(standard=standard) if standard else train_model()

    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            'message': 'Model trained successfully',
            'accuracy': result['accuracy'],
            'samples': result['samples'],
            'standard': standard,
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def train_models_api(request):
    standard = request.data.get('standard')
    result = train_all_models(standard=standard) if standard else train_all_models()
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def semantic_search_api(request):
    query = request.data.get('query') or request.data.get('q')
    standard = request.data.get('standard')
    top_k = request.data.get('top_k', 5)

    if not query or not isinstance(query, str) or not query.strip():
        raise ValidationError({'query': 'A non-empty query string is required.'})

    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        top_k = 5

    engine = SemanticSearchEngine()
    try:
        result = engine.search(query=query.strip(), standard=standard, top_k=top_k)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(result)


class TrainingSampleViewSet(viewsets.ModelViewSet):
    queryset = TrainingSample.objects.select_related('document__norme').all()
    serializer_class = TrainingSampleSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated(), IsAdmin()]

    def get_queryset(self):
        standard = self.request.query_params.get('standard')
        qs = self.queryset

        if standard:
            qs = qs.filter(standard=standard)

        return qs.order_by('-created_at')


# ==================== ML DASHBOARD ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def norms_list_api(request):
    """Get list of all norms for ML Dashboard"""
    norms = Norme.objects.all().values('id', 'name', 'description')
    return Response(list(norms))


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def dataset_stats_api(request):
    """Get dataset statistics for a specific norm"""
    norm_id = request.query_params.get('norm_id')
    
    if not norm_id:
        return Response(
            {'error': 'norm_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        norme = Norme.objects.get(id=norm_id)
    except Norme.DoesNotExist:
        return Response(
            {'error': 'Norm not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    training_samples = TrainingSample.objects.filter(document__norme=norme)
    if training_samples.count() == 0:
        training_samples = TrainingSample.objects.filter(standard__iexact=norme.name)
        if training_samples.count() == 0:
            training_samples = TrainingSample.objects.filter(standard__iexact=norme.name.replace(' ', ''))

    total_samples = training_samples.count()
    valid_samples = training_samples.filter(label__iexact='approved').count()
    invalid_samples = training_samples.filter(label__iexact='rejected').count()
    rules_count = Rule.objects.filter(norme=norme).count()
    
    # Get recent samples for display
    samples = training_samples.order_by('-created_at')
    samples_serializer = TrainingSampleSerializer(samples, many=True)
    
    return Response({
        'norm_id': norme.id,
        'norm_name': norme.name,
        'total_samples': total_samples,
        'valid_samples': valid_samples,
        'invalid_samples': invalid_samples,
        'rules_count': rules_count,
        'balance_ratio': valid_samples / max(total_samples, 1),
        'samples': samples_serializer.data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def ml_train_api(request):
    """Train ML models for a specific norm"""
    norm_id = request.data.get('norm_id')
    
    if not norm_id:
        return Response(
            {'error': 'norm_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        norme = Norme.objects.get(id=norm_id)
    except Norme.DoesNotExist:
        return Response(
            {'error': 'Norm not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    result = train_all_models(standard=norme.name, norme_id=norme.id)
    
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def ml_models_api(request):
    """Get trained ML models for a specific norm"""
    norm_id = request.query_params.get('norm_id')
    
    if not norm_id:
        return Response(
            {'error': 'norm_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        norme = Norme.objects.get(id=norm_id)
    except Norme.DoesNotExist:
        return Response(
            {'error': 'Norm not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Placeholder: This should fetch model metrics from ML module
    # For now, return a sample structure
    result = train_all_models(standard=norme.name, norme_id=norme.id)
    
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def ml_test_document_api(request):
    """Test a document with selected ML model"""
    model_id = request.data.get('model_id')
    norm_id = request.data.get('norm_id')
    document_file = request.FILES.get('file')
    
    if not document_file:
        return Response(
            {'error': 'file is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not model_id:
        return Response(
            {'error': 'model_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    standard = 'ISO9001'
    if norm_id:
        try:
            norme = Norme.objects.get(id=norm_id)
            standard = norme.name
        except Norme.DoesNotExist:
            return Response(
                {'error': 'Norm not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    elif request.data.get('standard'):
        standard = request.data.get('standard')

    try:
        text = extract_text(document_file)
        raw_features = extract_features(text, standard)
        if not raw_features:
            return Response(
                {'error': 'Could not extract features from document.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        model = load_trained_model(model_id, standard)
        feature_values = build_feature_vector(raw_features, standard)
        if not feature_values:
            return Response(
                {'error': 'Invalid document feature vector.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        prediction_value = model.predict([feature_values])[0]
        prediction = 'APPROVED' if int(prediction_value) == 1 else 'REJECTED'

        evidence_score = compute_score(raw_features)[0]
        probability_score = None
        if hasattr(model, 'predict_proba'):
            proba = model.predict_proba([feature_values])[0]
            probability_score = int(round(proba[1] * 100))

        compliance_score = evidence_score
        model_confidence = probability_score

        rules_predictions = []
        for rule, result in raw_features.items():
            rules_predictions.append({
                'rule': rule,
                'prediction': 'VALID' if result.get('status') == 1 else 'INVALID',
                'confidence': 90 if result.get('status') == 1 else 35,
                'evidence': result.get('evidence') or 'Aucune évidence détectée',
            })

        response_data = {
            'compliance_score': compliance_score,
            'prediction': prediction,
            'rules': rules_predictions,
            'model_id': model_id,
            'standard': standard,
        }
        if model_confidence is not None:
            response_data['model_confidence'] = model_confidence

        return Response(response_data)
    except FileNotFoundError as exc:
        return Response(
            {'error': str(exc)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as exc:
        return Response(
            {'error': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

