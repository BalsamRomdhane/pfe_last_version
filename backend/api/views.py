import json
import logging
import re
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.views import APIView

from .models import Norme, Rule, Document, Validation, TrainingSample, RuleTrainingSample, create_training_sample
from .serializers import (
    NormeSerializer,
    RuleSerializer,
    DocumentSerializer,
    DocumentDetailSerializer,
    ValidationSerializer,
    TrainingSampleSerializer,
    RuleTrainingSampleSerializer,
)
from .utils import extract_text, extract_features, compute_score
from .utils_dataset import generate_all_iso9001_datasets, export_datasets_for_norm
from authentication.permissions import IsAdmin, IsTeamLead, IsTeamLeadOrAdmin, IsEmployee
from compliance_engine import ComplianceEngine
try:
    from ml.search import SemanticSearchEngine
    from ml.train import train_model
    from ml.train_models import train_all_models
    from ml.search import build_and_persist_evidence_index, load_evidence_index_metadata
except Exception as e:
    print(f"Warning: Could not import ML modules: {e}")
    SemanticSearchEngine = None
    train_model = None
    train_all_models = None
    build_and_persist_evidence_index = None
    load_evidence_index_metadata = None

logger = logging.getLogger(__name__)


def recalculate_document_status(document):
    if document.is_finalized:
        return document.status

    total_rules = document.norme.rules.count()
    validations = Validation.objects.filter(document=document)
    validated_count = validations.exclude(is_valid__isnull=True).count()

    if total_rules == 0 or validated_count < total_rules:
        new_status = Document.Status.REVIEWING
    else:
        new_status = Document.Status.REVIEWING

    if document.status != new_status:
        document.status = new_status
        document.save(update_fields=['status'])

    return new_status


class ExtractFeaturesView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        document_file = request.FILES.get('file')
        norme_id = request.data.get('norme_id') or request.data.get('standard')

        if not document_file:
            raise ValidationError({'file': 'This field is required.'})
        if not norme_id:
            raise ValidationError({'standard': 'This field is required.'})

        # Try to get norme by ID or name
        try:
            norme = Norme.objects.prefetch_related('rules').get(id=norme_id)
        except (Norme.DoesNotExist, ValueError):
            # Try by name
            try:
                norme = Norme.objects.prefetch_related('rules').get(name__iexact=norme_id)
            except Norme.DoesNotExist:
                raise ValidationError({'standard': f'Norm "{norme_id}" not found.'})

        # Extract text from document using the existing file extractor
        text = extract_text(document_file)

        # Analyze document through the central compliance engine
        engine = ComplianceEngine()
        result = engine.analyze_document(text=text, norme=norme, document=None)

        return Response(result)


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

    def perform_destroy(self, instance):
        from django.db import IntegrityError
        try:
            instance.delete()
        except IntegrityError as e:
            # Check if there are documents linked to this norme
            doc_count = Document.objects.filter(norme=instance).count()
            if doc_count > 0:
                raise ValidationError({
                    'detail': f'Cannot delete norme "{instance.name}" because {doc_count} document(s) are still linked to it. Please delete or reassign the documents first.'
                })
            raise ValidationError({'detail': str(e)})


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

        final_statuses = [Document.Status.APPROVED, Document.Status.REJECTED]
        review_data = {
            'final_decision': document.final_decision,
            'decision_reason': document.decision_reason,
            'reviewer_comment': document.reviewer_comment,
            'approved_by': document.approved_by,
            'approved_at': document.approved_at,
            'review_completed_at': document.review_completed_at,
            'is_finalized': document.is_finalized,
        }

        if status_value in final_statuses:
            review_data.update({
                'final_decision': status_value,
                'decision_reason': request.data.get('decision_reason', document.decision_reason),
                'reviewer_comment': request.data.get('reviewer_comment', document.reviewer_comment),
                'approved_by': user.username,
                'approved_at': timezone.now(),
                'review_completed_at': timezone.now(),
                'is_finalized': True,
            })
            self._sync_direct_validations(document, status_value, user.username)
        else:
            review_data.update({
                'final_decision': Document.Status.PENDING,
                'is_finalized': False,
            })

        teamlead_username = document.teamlead_username
        if 'TEAMLEAD' in roles or not teamlead_username:
            teamlead_username = user.username

        Document.objects.filter(pk=document.pk).update(
            status=status_value,
            teamlead_username=teamlead_username,
            **{k: v for k, v in review_data.items() if v is not None},
        )
        document.refresh_from_db()
        if document.status in final_statuses:
            create_training_sample(document)
        try:
            export_datasets_for_norm(document.norme)
        except Exception:
            pass
        serializer = self.get_serializer(document)
        return Response({
            'message': 'Status updated.',
            'status': document.status,
            'document': serializer.data,
        })

    def _sync_direct_validations(self, document, status_value, teamlead_username):
        """Create or update validations for every rule during direct approval/rejection."""
        rules = document.norme.rules.all()
        is_valid_default = (status_value == Document.Status.APPROVED)
        
        if is_valid_default:
            evidence_text = "Document valide directement par le teamlead - toutes les regles conformes."
        else:
            evidence_text = "Document rejete directement par le teamlead - non-conformite detectee."
        
        for rule in rules:
            Validation.objects.update_or_create(
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

    def finalize_document(self, document, final_decision, decision_reason='', reviewer_comment='', reviewer_username=None):
        if final_decision not in [Document.Status.APPROVED, Document.Status.REJECTED]:
            raise ValidationError({'final_decision': 'Invalid final decision. Must be "approved" or "rejected".'})

        document.final_decision = final_decision
        document.decision_reason = decision_reason or document.decision_reason
        document.reviewer_comment = reviewer_comment or document.reviewer_comment
        document.approved_by = reviewer_username or document.approved_by
        document.approved_at = timezone.now()
        document.review_completed_at = timezone.now()
        document.is_finalized = True
        document.status = final_decision
        document.teamlead_username = reviewer_username or document.teamlead_username
        document.save(update_fields=['final_decision', 'decision_reason', 'reviewer_comment', 'approved_by', 'approved_at', 'review_completed_at', 'is_finalized', 'status', 'teamlead_username'])

        try:
            sample = TrainingSample.objects.get(document=document)
            sample.final_decision = final_decision
            sample.decision_reason = decision_reason or sample.decision_reason
            sample.save(update_fields=['final_decision', 'decision_reason'])
        except TrainingSample.DoesNotExist:
            pass

        RuleTrainingSample.objects.filter(document=document).update(final_document_decision=final_decision)

    def perform_create(self, serializer):
        validation = serializer.save(teamlead_username=self.request.user.username)
        self.recalculate_document_status(validation.document)
        create_training_sample(validation.document)
        try:
            # regenerate datasets for the norme of this document
            export_datasets_for_norm(validation.document.norme)
        except Exception:
            # do not break validation flow on dataset generation errors
            pass

    def perform_update(self, serializer):
        validation = serializer.save()
        self.recalculate_document_status(validation.document)
        create_training_sample(validation.document)
        try:
            export_datasets_for_norm(validation.document.norme)
        except Exception:
            pass

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

        final_decision = request.data.get('final_decision')
        decision_reason = request.data.get('decision_reason', '')
        reviewer_comment = request.data.get('reviewer_comment', '')

        if final_decision:
            self.finalize_document(
                document=document,
                final_decision=final_decision,
                decision_reason=decision_reason,
                reviewer_comment=reviewer_comment,
                reviewer_username=request.user.username,
            )
        else:
            self.recalculate_document_status(document)

        document.refresh_from_db()
        create_training_sample(document)
        try:
            export_datasets_for_norm(document.norme)
        except Exception:
            pass
        document.teamlead_username = request.user.username
        document.save(update_fields=['teamlead_username'])

        serializer = ValidationSerializer(
            Validation.objects.filter(document=document),
            many=True,
            context={'request': request},
        )
        
        # Return updated document as well
        document.refresh_from_db()
        doc_serializer = DocumentDetailSerializer(document, context={'request': request})
        
        return Response(
            {
                'status': document.status,
                'document': doc_serializer.data,
                'validations': serializer.data,
                'compliance_score': (
                    Validation.objects.filter(document=document, is_valid=True).count() * 100
                    // max(document.norme.rules.count(), 1)
                ),
                'final_decision': document.final_decision,
                'decision_reason': document.decision_reason,
                'reviewer_comment': document.reviewer_comment,
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
        # Allow unauthenticated read access during debugging so frontend can load datasets
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def get_authenticators(self):
        # During debugging, skip authentication for list/retrieve so unauthenticated clients can access datasets
        if getattr(self, 'action', None) in ['list', 'retrieve']:
            return []
        return super().get_authenticators()

    def get_queryset(self):
        standard = self.request.query_params.get('standard')
        norm_id = self.request.query_params.get('norm')
        qs = self.queryset

        if standard:
            qs = qs.filter(standard=standard)
        if norm_id:
            try:
                qs = qs.filter(norm_id=int(norm_id))
            except (TypeError, ValueError):
                qs = qs.filter(document__norme__name__iexact=norm_id)

        return qs.order_by('-created_at')


class RuleTrainingSampleViewSet(viewsets.ModelViewSet):
    queryset = RuleTrainingSample.objects.select_related('document', 'rule', 'norm').all()
    serializer_class = RuleTrainingSampleSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated(), IsAdmin()]
        # Allow unauthenticated read access during debugging so frontend can load KB
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def get_authenticators(self):
        if getattr(self, 'action', None) in ['list', 'retrieve']:
            return []
        return super().get_authenticators()

    def get_queryset(self):
        qs = self.queryset
        norm_id = self.request.query_params.get('norm')
        standard = self.request.query_params.get('standard')
        rule = self.request.query_params.get('rule')
        document_id = self.request.query_params.get('document')
        label = self.request.query_params.get('label')

        if norm_id:
            try:
                norm_id_int = int(norm_id)
                qs = qs.filter(norm_id=norm_id_int)
            except (TypeError, ValueError):
                qs = qs.filter(norm__name__iexact=norm_id)

        if standard:
            qs = qs.filter(norm__name__iexact=standard)

        if rule:
            try:
                qs = qs.filter(rule_id=int(rule))
            except (TypeError, ValueError):
                qs = qs.filter(rule__title__icontains=rule)

        if document_id:
            try:
                qs = qs.filter(document_id=int(document_id))
            except (TypeError, ValueError):
                pass

        if label:
            qs = qs.filter(label__iexact=label)

        if norm_id and not qs.exists():
            self._backfill_rule_training_samples(norm_id)
            try:
                qs = self.queryset.filter(norm_id=int(norm_id))
            except (TypeError, ValueError):
                qs = self.queryset.filter(norm__name__iexact=norm_id)

        return qs.order_by('-created_at')

    def _backfill_rule_training_samples(self, norm_id):
        try:
            norm_id_int = int(norm_id)
        except (TypeError, ValueError):
            norm_id_int = None

        validations = Validation.objects.filter(rule__norme_id=norm_id_int) if norm_id_int else Validation.objects.filter(rule__norme__name__iexact=norm_id)
        validations = validations.select_related('document', 'rule__norme')

        for validation in validations.iterator():
            RuleTrainingSample.objects.update_or_create(
                document=validation.document,
                rule=validation.rule,
                defaults={
                    'norm': validation.rule.norme,
                    'rule_title': validation.rule.title or '',
                    'rule_description': validation.rule.description or '',
                    'document_text': '',
                    'evidence_text': validation.evidence_text or '',
                    'reviewer_comment': validation.comment or '',
                    'recommendation': validation.rule.action or '',
                    'confidence_score': 0.0,
                    'semantic_score': 0.0,
                    'label': 'approved' if validation.is_valid else ('rejected' if validation.is_valid is False else 'pending'),
                }
            )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def norms_list_api(request):
    """Get list of all normes with their rules count"""
    normes = Norme.objects.prefetch_related('rules').all()
    data = []
    for norme in normes:
        data.append({
            'id': norme.id,
            'name': norme.name,
            'description': norme.description,
            'rules_count': norme.rules.count(),
        })
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def dataset_stats_api(request):
    """Get training dataset statistics for a specific norm or standard"""
    norm_id = request.query_params.get('norm_id')
    standard = request.query_params.get('standard')
    
    # Determine query filter
    query_filter = {}
    selected_norm = None
    
    if norm_id:
        try:
            selected_norm = Norme.objects.get(pk=norm_id)
            standard = selected_norm.name
            query_filter['standard'] = standard
        except (Norme.DoesNotExist, ValueError):
            pass
    elif standard:
        query_filter['standard'] = standard
    
    # Get samples matching filter
    samples_qs = TrainingSample.objects.filter(**query_filter) if query_filter else TrainingSample.objects.all()
    labeled_samples_qs = samples_qs.filter(approved__in=[True, False])
    pending_samples_qs = samples_qs.filter(approved__isnull=True)
    
    # total samples should be all samples matching the filter, not only labeled ones
    total_samples = samples_qs.count()
    valid_samples = samples_qs.filter(approved=True).count()
    invalid_samples = samples_qs.filter(approved=False).count()
    pending_samples = samples_qs.filter(approved__isnull=True).count()
    
    # Get rules count for the selected norm/standard
    rules_count = 0
    if selected_norm:
        rules_count = selected_norm.rules.count()
    elif standard:
        norme = Norme.objects.filter(name__iexact=standard).first()
        rules_count = norme.rules.count() if norme else 0
    
    sample_list = list(
        labeled_samples_qs.values(
            'id',
            'label',
            'approved',
            'confidence_score',
            'compliance_score',
            'total_rules',
            'valid_rules_count',
            'invalid_rules_count',
            'feature_vector',
            'rule_results_json',
            'standard',
            'created_at',
        ).order_by('-created_at')[:100]
    )

    logger.debug(
        "dataset_stats_api norm_id=%s standard=%s filter=%s total=%d valid=%d invalid=%d pending=%d samples_returned=%d",
        norm_id,
        standard,
        query_filter,
        total_samples,
        valid_samples,
        invalid_samples,
        pending_samples,
        len(sample_list),
    )

    return Response({
        'total_samples': total_samples,
        'valid_samples': valid_samples,
        'invalid_samples': invalid_samples,
        'approved_samples': valid_samples,   # alias for MLDashboard compatibility
        'pending_samples': pending_samples,
        'rules_count': rules_count,
        'selected_norm': {
            'id': selected_norm.id if selected_norm else None,
            'name': selected_norm.name if selected_norm else None,
        } if selected_norm else None,
        'samples': sample_list,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def ml_train_api(request):
    """Train ML models for a specific standard or norme id."""
    standard = request.data.get('standard')
    norme_id = request.data.get('norm_id') or request.data.get('norme_id')

    if not standard and not norme_id:
        return Response(
            {'error': 'Standard or norm_id is required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not standard and norme_id:
        try:
            norme = Norme.objects.get(pk=norme_id)
            standard = norme.name
        except (Norme.DoesNotExist, ValueError):
            return Response(
                {'error': f'Norme with id {norme_id} does not exist.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    try:
        result = train_all_models(standard=standard, norme_id=norme_id)
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ml_models_api(request):
    """Get list of available ML models"""
    import os
    from ml.train_models import get_model_path, sanitize_standard

    models_dir = os.path.join(os.path.dirname(__file__), '..', 'ml', 'models')
    allowed_algorithms = ["RandomForest", "LogisticRegression", "GradientBoosting", "BiLSTM"]

    # Build a standard prefix to strip based on the requested norm
    norm_id = request.query_params.get('norm_id')
    standard_prefix = None
    if norm_id:
        try:
            norm = Norme.objects.get(pk=norm_id)
            standard_prefix = sanitize_standard(norm.name) + '_'
        except (Norme.DoesNotExist, ValueError):
            pass

    if not os.path.exists(models_dir):
        return Response({'models': [{
            'name': algo,
            'path': None,
            'exists': False,
        } for algo in allowed_algorithms]})

    def normalize_model_name(raw_name: str) -> str:
        cleaned = raw_name
        # Strip any standard prefix (e.g. ISO_9001___Controle_..._RandomForest -> RandomForest)
        if standard_prefix and cleaned.startswith(standard_prefix):
            cleaned = cleaned[len(standard_prefix):]
        else:
            # Legacy: strip ISO9001_ prefix
            for prefix in ('ISO9001_', 'ISO_9001_', 'ISO9001-', 'ISO_9001-'):
                if cleaned.startswith(prefix):
                    cleaned = cleaned[len(prefix):]
                    break
        if cleaned in allowed_algorithms:
            return cleaned
        # Try splitting on _ and taking the last part
        parts = cleaned.split('_')
        if parts and parts[-1] in allowed_algorithms:
            return parts[-1]
        return raw_name

    model_info = {algo: {'name': algo, 'path': None, 'exists': False, 'accuracy': None, 'precision': None, 'recall': None, 'f1_score': None, 'sample_count': None, 'trained_date': None} for algo in allowed_algorithms}

    for file in os.listdir(models_dir):
        if not file.endswith('.pkl'):
            continue
        raw_name = file.replace('.pkl', '')
        algorithm = normalize_model_name(raw_name)
        if algorithm not in model_info:
            continue
        model_path = os.path.join(models_dir, file)
        if os.path.exists(model_path):
            # Prefer norm-specific model over legacy generic model
            existing = model_info[algorithm]
            if not existing['exists'] or (standard_prefix and raw_name.startswith(standard_prefix)):
                import datetime
                mtime = os.path.getmtime(model_path)
                trained_date = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                model_info[algorithm] = {
                    'name': algorithm,
                    'path': model_path,
                    'exists': True,
                    'accuracy': None,
                    'precision': None,
                    'recall': None,
                    'f1_score': None,
                    'sample_count': None,
                    'trained_date': trained_date,
                }

    return Response({'models': list(model_info.values())})


# ===== NOUVELLES VUES POUR L'ANALYSE DE CONFORMITÉ NLP =====

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_document_compliance_api(request):
    """
    Analyze document compliance using classical NLP/ML techniques.

    Expected JSON payload:
    {
        "document_text": "Full text of the document to analyze",
        "standard": "ISO9001"  # optional, defaults to ISO9001
    }

    Or with file upload:
    - file: Document file (PDF/DOCX)
    - standard: ISO standard (optional)
    """
    from ml.services import compliance_service

    try:
        standard = request.data.get('standard', '')

        # Resolve the Norme object for ComplianceEngine
        # Try exact match, then partial, then first available norm
        norme = None
        if standard:
            norme = (
                Norme.objects.filter(name__iexact=standard).first()
                or Norme.objects.filter(name__icontains=standard).first()
                or Norme.objects.filter(name__icontains='iso').first()
            )
        if not norme:
            norme = Norme.objects.first()

        if not standard and norme:
            standard = norme.name

        # Check if file upload or text input
        if 'file' in request.FILES:
            uploaded_file = request.FILES['file']
            import tempfile
            import os as _os

            suffix = _os.path.splitext(uploaded_file.name)[1] or '.pdf'
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                for chunk in uploaded_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            try:
                # Extract text first
                raw_text = extract_text(uploaded_file)
                file_size = _os.path.getsize(tmp_path)
            finally:
                _os.unlink(tmp_path)

            document_text = raw_text

        elif 'document_text' in request.data:
            document_text = request.data['document_text']
            file_size = None
        else:
            return Response(
                {'error': 'Either "file" or "document_text" must be provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Primary: use ComplianceEngine (keyword/pattern matching against real DB rules)
        if norme:
            engine = ComplianceEngine()
            result = engine.analyze_document(text=document_text, norme=norme, document=None)
            # Normalise field names so the frontend gets consistent keys
            result.setdefault('standard', standard)
            result.setdefault('matches', result.get('detected_rules', []))
            result.setdefault('detected_rules', result.get('detected_rules', []))
            result.setdefault('missing_rules', [r['title'] for r in result.get('invalid_rules', [])])
            result.setdefault('compliance_score', result.get('compliance', 0))
            if file_size is not None:
                result['file_info'] = {
                    'file_size': file_size,
                    'text_length': len(document_text),
                }
        else:
            # Fallback: TF-IDF compliance_service
            if file_size is not None:
                result = compliance_service.analyze_document_text(document_text, standard)
                result['file_info'] = {'file_size': file_size, 'text_length': len(document_text)}
            else:
                result = compliance_service.analyze_document_text(document_text, standard)

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': f'Analysis failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_supported_standards_api(request):
    """Get list of supported ISO standards for compliance analysis."""
    from ml.services import compliance_service

    try:
        standards = compliance_service.get_supported_standards()
        return Response({'standards': standards}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_standard_rules_api(request, standard):
    """Get rules for a specific ISO standard."""
    from ml.services import compliance_service

    try:
        rules = compliance_service.get_standard_rules(standard)
        return Response({
            'standard': standard,
            'rules': rules,
            'total_rules': len(rules)
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def retrain_compliance_models_api(request):
    """Retrain compliance analysis models for a specific standard."""
    from ml.services import compliance_service

    try:
        standard = request.data.get('standard', 'ISO9001')
        result = compliance_service.retrain_models(standard)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def update_similarity_threshold_api(request):
    """Update similarity threshold for compliance detection."""
    from ml.services import compliance_service

    try:
        threshold = request.data.get('threshold')
        if threshold is None:
            return Response(
                {'error': 'Threshold value is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        threshold = float(threshold)
        if not 0.0 <= threshold <= 1.0:
            return Response(
                {'error': 'Threshold must be between 0.0 and 1.0'},
                status=status.HTTP_400_BAD_REQUEST
            )

        success = compliance_service.update_similarity_threshold(threshold)
        if success:
            return Response({
                'message': f'Similarity threshold updated to {threshold}',
                'threshold': threshold
            }, status=status.HTTP_200_OK)
        else:
            return Response(
                {'error': 'Failed to update threshold'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except ValueError:
        return Response(
            {'error': 'Invalid threshold value'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_compliance_service_status_api(request):
    """Get current status of the compliance analysis service."""
    from ml.services import compliance_service

    try:
        status_info = compliance_service.get_service_status()
        return Response(status_info, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ml_test_document_api(request):
    """Test document against ML models"""
    document_file = request.FILES.get('file')
    standard = request.data.get('standard')

    # Fallback: resolve standard from norm_id if not provided directly
    if not standard:
        norm_id = request.data.get('norm_id')
        if norm_id:
            try:
                norm = Norme.objects.get(pk=norm_id)
                standard = norm.name
            except Norme.DoesNotExist:
                pass

    if not document_file:
        return Response({'error': 'File is required'}, status=status.HTTP_400_BAD_REQUEST)
    if not standard:
        return Response({'error': 'Standard is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        text = extract_text(document_file)
        features = extract_features(text, standard)
        compliance, valid_rules, invalid_rules = compute_score(features)

        # Try to use ML model if available
        ml_prediction = None
        try:
            from ml.train_models import load_trained_model
            model = load_trained_model('compliance_classifier', standard)
            if model:
                # Convert features to format expected by model
                import numpy as np
                feature_vector = np.array([list(features.values())])
                prediction = model.predict(feature_vector)[0]
                ml_prediction = 'approved' if prediction == 1 else 'rejected'
        except Exception as e:
            print(f"ML prediction failed: {e}")

        return Response({
            'standard': standard,
            'compliance_score': compliance,
            'valid_rules': valid_rules,
            'invalid_rules': invalid_rules,
            'ml_prediction': ml_prediction,
            'features': features,
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def ml_train_evidence_api(request):
    """Build and persist the evidence FAISS index from RuleTrainingSample rows."""
    if build_and_persist_evidence_index is None:
        return Response({'error': 'Indexing functionality unavailable'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    standard = request.data.get('standard')
    norme_id = request.data.get('norm_id') or request.data.get('norme_id')

    if not standard and norme_id:
        try:
            norme = Norme.objects.get(pk=norme_id)
            standard = norme.name
        except (Norme.DoesNotExist, ValueError):
            pass

    try:
        meta = build_and_persist_evidence_index(standard=standard, norme_id=norme_id)
        return Response({
            'message': 'Evidence index built successfully',
            'indexed_count': meta.get('indexed_evidences', 0),
            'indexed_vectors': meta.get('indexed_evidences', 0),
            'total_evidences': meta.get('total_evidences', 0),
            'embedding_model': meta.get('embedding_model'),
            'vector_dim': meta.get('vector_dim'),
            'last_trained': meta.get('last_trained'),
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def evidence_index_api(request):
    """Build and persist evidence FAISS index from RuleTrainingSample rows."""
    if build_and_persist_evidence_index is None:
        return Response({'error': 'Indexing functionality unavailable'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    standard = request.data.get('standard') or request.data.get('standard_name')
    norm_id = request.data.get('norm_id') or request.data.get('norme_id')
    try:
        result = build_and_persist_evidence_index(standard=standard, norme_id=norm_id)
        return Response({'message': 'Evidence index built', 'metadata': result}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def evidence_status_api(request):
    """Return authoritative evidence indexing status and coverage."""
    # Core counts from DB
    try:
        total = int(RuleTrainingSample.objects.count())
    except Exception:
        total = 0

    # Aggregate other useful metrics
    try:
        rules_covered = RuleTrainingSample.objects.values('rule_id').distinct().count()
    except Exception:
        rules_covered = 0

    try:
        approved_patterns = RuleTrainingSample.objects.filter(label__iexact='approved').count()
    except Exception:
        approved_patterns = 0

    try:
        rejected_patterns = RuleTrainingSample.objects.filter(label__iexact='rejected').count()
    except Exception:
        rejected_patterns = 0

    # Load persisted index metadata when available
    meta = None
    if load_evidence_index_metadata is not None:
        try:
            meta = load_evidence_index_metadata()
        except Exception:
            meta = None

    indexed = int(meta.get('indexed_evidences')) if meta and isinstance(meta.get('indexed_evidences'), int) else 0
    embedding_model = meta.get('embedding_model') if meta else None
    last_trained = meta.get('last_trained') if meta else None
    vector_dim = int(meta.get('vector_dim')) if meta and isinstance(meta.get('vector_dim'), int) else None

    coverage = 0.0
    if total > 0:
        coverage = round((indexed / total) * 100.0, 2)

    train_status = 'READY' if indexed > 0 else ('EMPTY' if total == 0 else 'NOT_TRAINED')

    return Response({
        'total_evidences': total,
        'indexed_evidences': indexed,
        'coverage_percent': coverage,
        'rules_covered': rules_covered,
        'approved_patterns': approved_patterns,
        'rejected_patterns': rejected_patterns,
        'embedding_model': embedding_model,
        'vector_dim': vector_dim,
        'last_trained': last_trained,
        'train_status': train_status,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def rule_memory_api(request):
    """Return all RuleTrainingSample rows as the knowledge base (no pagination)."""
    try:
        qs = RuleTrainingSample.objects.select_related('rule', 'norm', 'document').order_by('-created_at')

        # Simple pagination parameters
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except Exception:
            page = 1
        try:
            page_size = int(request.query_params.get('page_size', 25))
        except Exception:
            page_size = 25
        page_size = min(max(1, page_size), 200)

        offset = (page - 1) * page_size
        limit = offset + page_size

        total = qs.count()
        items = qs[offset:limit]

        serializer = RuleTrainingSampleSerializer(items, many=True, context={'request': request})

        return Response({
            'total': total,
            'page': page,
            'page_size': page_size,
            'items': serializer.data,
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search_evidence_api(request):
    """Search persisted evidence index for a text query and return nearest RuleTrainingSample rows."""
    query = request.data.get('query') or request.data.get('q')
    norm_id = request.data.get('norm_id') or request.data.get('norm')
    try:
        top_k = int(request.data.get('top_k', 5))
    except Exception:
        top_k = 5

    if not query or not isinstance(query, str) or not query.strip():
        raise ValidationError({'query': 'A non-empty query string is required.'})

    try:
        from ml.search import load_evidence_index, embed_query_vector
    except Exception as e:
        return Response({'error': 'Search helpers unavailable: ' + str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        index, ids, vectorizer, vectors, meta = load_evidence_index()
    except Exception as e:
        return Response({'error': 'Evidence index not available: ' + str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # embed query
    try:
        qvec = embed_query_vector(query, model_name=meta.get('embedding_model') if meta else None, vectorizer=vectorizer)
        if qvec is None:
            return Response({'error': 'Failed to embed query'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        return Response({'error': 'Embedding failed: ' + str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # perform search using FAISS if present, otherwise use TF-IDF vectors fallback
    try:
        import numpy as np
        q = np.asarray(qvec, dtype=np.float32)

        hits = []
        if index is not None and getattr(index, 'ntotal', 0) > 0:
            distances, indices = index.search(q, min(top_k, index.ntotal))
            for dist, idx_list in zip(distances.tolist(), indices.tolist()):
                for d, idx in zip(dist, idx_list):
                    if idx < 0 or idx >= len(ids):
                        continue
                    sample_id = ids[idx]
                    hits.append({'id': sample_id, 'distance': float(d)})
        elif vectorizer is not None and vectors is not None:
            if q.ndim == 1:
                q = q.reshape(1, -1)
            if q.shape[1] != vectors.shape[1]:
                return Response({'error': 'Query vector dimension does not match stored evidence vectors'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            similarities = cosine_similarity(q, vectors.astype(np.float32))[0]
            top_indices = np.argsort(similarities)[::-1][:min(top_k, len(similarities))]
            for idx in top_indices:
                sample_id = ids[idx]
                hits.append({'id': sample_id, 'distance': float(similarities[idx])})
        else:
            return Response({'error': 'Evidence search index is not available on server'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # fetch RuleTrainingSample rows
        sample_ids = [h['id'] for h in hits]
        samples = list(RuleTrainingSample.objects.filter(id__in=sample_ids).select_related('rule').all())
        samples_map = {s.id: s for s in samples}

        results = []
        for h in hits:
            s = samples_map.get(h['id'])
            if not s:
                continue
            similarity = None
            try:
                # distances are inner product; clip to [0,1]
                similarity = max(0.0, min(1.0, float(h['distance'])))
            except Exception:
                similarity = None

            results.append({
                'id': s.id,
                'similarity': round((similarity or 0) * 100),
                'rule': s.rule_title or (s.rule.title if getattr(s, 'rule', None) else ''),
                'evidence': s.evidence_text,
                'comment': s.reviewer_comment,
                'recommendation': s.recommendation,
                'decision': s.label,
                'date': s.created_at,
            })

        return Response({'query': query, 'results': results})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
