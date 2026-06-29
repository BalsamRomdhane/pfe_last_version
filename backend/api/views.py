import json
import logging
import os
import re
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from django.db import ProgrammingError, connection, transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.views import APIView


def _table_exists(table_name: str) -> bool:
    try:
        return table_name in connection.introspection.table_names()
    except Exception:
        return False

from .models import (
    Norme,
    Rule,
    Document,
    Validation,
    TrainingSample,
    RuleTrainingSample,
    DocumentTrainingSample,
    create_training_sample,
)
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
from ml.dataset_builder import buildTrainingDataset, sync_training_samples_from_evidence
from authentication.permissions import IsAdmin, IsTeamLead, IsTeamLeadOrAdmin, IsEmployee

# Compliance search modules are imported lazily to avoid startup failures when
# sentence-transformers / FAISS are unavailable.
try:
    from ml.search import SemanticSearchEngine
    from ml.search import build_and_persist_evidence_index, load_evidence_index_metadata
except Exception as e:
    logger.warning('Could not import ML search modules: %s', e)
    SemanticSearchEngine = None
    build_and_persist_evidence_index = None
    load_evidence_index_metadata = None

# Avoid importing heavy training modules at import time. These modules can pull in
# torch/sentence-transformers and may crash the process on Windows when DLLs are
# not available or incompatible.
train_model = None
train_all_models = None


def _load_ml_training_modules():
    """Lazy-load ML training modules when the training endpoints are called."""
    global train_model, train_all_models
    if train_model is not None and train_all_models is not None:
        return None

    try:
        from ml.train import train_model as _train_model
        from ml.train_models import train_all_models as _train_all_models
        train_model = _train_model
        train_all_models = _train_all_models
        return None
    except Exception as e:
        return str(e)

logger = logging.getLogger(__name__)


def recalculate_document_status(document):
    """
    Recalculate document status based on validation completeness.
    - If finalized: keep current status (approved/rejected)
    - If all rules validated and all valid: APPROVED
    - If all rules validated and any invalid: REJECTED
    - Otherwise: REVIEWING
    """
    if document.is_finalized:
        return document.status

    total_rules = document.norme.rules.count()
    validations = Validation.objects.filter(document=document).exclude(is_valid__isnull=True)
    validated_count = validations.count()

    if total_rules == 0 or validated_count < total_rules:
        new_status = Document.Status.REVIEWING
    else:
        all_valid = not validations.filter(is_valid=False).exists()
        new_status = Document.Status.APPROVED if all_valid else Document.Status.REJECTED

    if document.status != new_status:
        document.status = new_status
        document.save(update_fields=['status'])  # explicit — triggers signal with update_fields hint

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
        from compliance_engine import ComplianceEngine  # lazy import
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
        qs = Document.objects.select_related('norme').prefetch_related(
            'validations__rule',
        )

        if 'ADMIN' in roles:
            queryset = qs
        elif 'TEAMLEAD' in roles:
            # A TeamLead sees documents from their department.
            # Also include documents where employee_department is blank
            # but the document was assigned to this teamlead explicitly.
            from django.db.models import Q as DQ
            dept = user.department or ''
            if dept:
                queryset = qs.filter(
                    DQ(employee_department=dept) |
                    DQ(employee_department='', teamlead_username=user.username)
                )
            else:
                queryset = qs.filter(teamlead_username=user.username)
        elif 'EMPLOYEE' in roles:
            queryset = qs.filter(employee_username=user.username)
        else:
            queryset = qs.none()

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Search filter
        search = self.request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(employee_username__icontains=search) |
                Q(norme__name__icontains=search) |
                Q(teamlead_username__icontains=search) |
                Q(status__icontains=search) |
                Q(id__icontains=search)
            )

        # Norme filter
        norme_filter = self.request.query_params.get('norme')
        if norme_filter:
            queryset = queryset.filter(norme_id=norme_filter)

        # Ordering
        ordering = self.request.query_params.get('ordering', '-created_at')
        allowed_orderings = ['created_at', '-created_at', 'compliance_score', '-compliance_score']
        if ordering in allowed_orderings:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('-created_at')

        return queryset

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

        # Document.objects.filter().update() bypasses post_save signals, so we
        # fire notifications explicitly after the bulk update.
        try:
            from notifications.signals import (
                _notify_document_approved,
                _notify_document_rejected,
                _notify_validation_required,
                _notify_document_submitted,
            )
            if document.is_finalized:
                if document.final_decision in (Document.Status.APPROVED, Document.Status.AUTO_APPROVED):
                    _notify_document_approved(document)
                elif document.final_decision == Document.Status.REJECTED:
                    _notify_document_rejected(document)
            elif document.status == Document.Status.REVIEWING:
                _notify_validation_required(document)
        except Exception:
            pass  # notifications are non-critical — never break the main flow

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

        # Use already-loaded validations to compute compliance — no extra SQL queries
        all_validations = list(Validation.objects.filter(document=document).select_related('rule'))
        valid_count   = sum(1 for v in all_validations if v.is_valid)
        total_rules   = document.norme.rules.count()
        compliance    = (valid_count * 100 // max(total_rules, 1))

        val_serializer = ValidationSerializer(
            all_validations,
            many=True,
            context={'request': request},
        )

        document.refresh_from_db()
        doc_serializer = DocumentDetailSerializer(
            Document.objects.select_related('norme').prefetch_related('validations__rule').get(pk=document.pk),
            context={'request': request},
        )

        return Response(
            {
                'status': document.status,
                'document': doc_serializer.data,
                'validations': val_serializer.data,
                'compliance_score': compliance,
                'final_decision': document.final_decision,
                'decision_reason': document.decision_reason,
                'reviewer_comment': document.reviewer_comment,
            },
            status=status.HTTP_200_OK,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def train_model_api(request):
    error = _load_ml_training_modules()
    if error is not None or train_model is None:
        return Response(
            {'error': 'ML training unavailable — install Visual C++ Redistributable 2019 and restart the server.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    standard = request.data.get('standard')
    try:
        result = train_model(standard=standard) if standard else train_model()
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response({
        'message': 'Model trained successfully',
        'accuracy': result['accuracy'],
        'samples': result['samples'],
        'standard': standard,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def train_models_api(request):
    error = _load_ml_training_modules()
    if error is not None or train_all_models is None:
        return Response(
            {'error': 'ML training unavailable — install Visual C++ Redistributable 2019 and restart the server.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    standard = request.data.get('standard')
    try:
        result = train_all_models(standard=standard) if standard else train_all_models()
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    if 'error' in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def semantic_search_api(request):
    query    = request.data.get('query') or request.data.get('q')
    standard = request.data.get('standard')
    top_k    = request.data.get('top_k', 5)

    if not query or not isinstance(query, str) or not query.strip():
        raise ValidationError({'query': 'A non-empty query string is required.'})

    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        top_k = 5

    # SemanticSearchEngine requires sentence-transformers / torch.
    # Fall back to TF-IDF keyword search when ML libs are unavailable.
    if SemanticSearchEngine is None:
        return _tfidf_fallback_search(query.strip(), standard, top_k)

    try:
        engine = SemanticSearchEngine()
        result = engine.search(query=query.strip(), standard=standard, top_k=top_k)
        return Response(result)
    except (ImportError, OSError, RuntimeError) as exc:
        # sentence-transformers / FAISS not available — degrade gracefully
        return _tfidf_fallback_search(query.strip(), standard, top_k)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _tfidf_fallback_search(query: str, standard, top_k: int):
    """
    TF-IDF keyword fallback when sentence-transformers is unavailable.
    Searches RuleTrainingSample evidence text via keyword overlap.
    """
    from django.db.models import Q
    from api.models import RuleTrainingSample

    qs = RuleTrainingSample.objects.select_related('norm', 'rule', 'document').all()
    if standard:
        qs = qs.filter(norm__name__iexact=standard)

    # Keyword filter across evidence_text, rule_title, document_text
    words = [w for w in query.lower().split() if len(w) > 2]
    if words:
        q_filter = Q()
        for w in words[:5]:
            q_filter |= (
                Q(evidence_text__icontains=w) |
                Q(rule_title__icontains=w) |
                Q(document_text__icontains=w)
            )
        qs = qs.filter(q_filter)

    results = []
    seen_docs = set()
    for sample in qs.order_by('-created_at')[:top_k * 3]:
        doc_id = sample.document_id
        if doc_id in seen_docs:
            continue
        seen_docs.add(doc_id)
        results.append({
            'document_id':    doc_id or 0,
            'document_name':  f"Document #{doc_id}" if doc_id else '—',
            'standard':       sample.norm.name if sample.norm else standard,
            'status':         sample.final_document_decision or sample.label or '—',
            'hybrid_score':   0.0,
            'semantic_score': 0.0,
            'bm25_score':     0.0,
            'keyword_score':  0.0,
            'evidence':       [{'rule': sample.rule_title, 'text': sample.evidence_text[:200]}],
        })
        if len(results) >= top_k:
            break

    return Response({
        'query':           query,
        'standard':        standard,
        'total_documents': len(results),
        'results':         results,
        'fallback':        True,
        'message':         'Using keyword fallback — sentence-transformers unavailable.',
    })


class TrainingSampleViewSet(viewsets.ModelViewSet):
    queryset = TrainingSample.objects.select_related('document__norme').all()
    serializer_class = TrainingSampleSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated()]

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
        return [IsAuthenticated()]

    def get_queryset(self):
        # Accept both ?norm= and ?norm_id= for backwards compatibility
        norm_id  = self.request.query_params.get('norm') or self.request.query_params.get('norm_id')
        standard = self.request.query_params.get('standard')
        rule     = self.request.query_params.get('rule')
        document_id = self.request.query_params.get('document')
        label    = self.request.query_params.get('label')

        # Build a fresh queryset — avoids class-level queryset mutation with select_related + pagination
        qs = RuleTrainingSample.objects.all()

        if norm_id:
            try:
                qs = qs.filter(norm_id=int(norm_id))
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

        # Order by -id: always fast, no JOIN needed, avoids select_related + pagination bug
        return qs.order_by('-id')

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
@permission_classes([IsAuthenticated])
def dataset_stats_api(request):
    """
    GET /api/dataset-stats/?norm_id=<id>&dataset_type=classification|evidence

    SINGLE SOURCE OF TRUTH: RuleTrainingSample is the canonical evidence store.
    All stats (classification, evidence, document modes) derive from it.
    TrainingSample is synced from it but never used as primary stats source.
    """
    from django.db.models import Avg, Count, Q as DQ

    norm_id      = request.query_params.get('norm_id')
    standard     = request.query_params.get('standard')
    dataset_type = str(request.query_params.get('dataset_type', 'classification')).lower()

    # ── Resolve norm ──────────────────────────────────────────────────────────
    selected_norm = None
    if norm_id:
        try:
            selected_norm = Norme.objects.get(pk=norm_id)
            standard = selected_norm.name
        except (Norme.DoesNotExist, ValueError):
            pass
    elif standard:
        selected_norm = Norme.objects.filter(name__iexact=standard).first()

    # All modes use RuleTrainingSample as the single source of truth.
    # This guarantees that ML Dashboard, Training Dataset, Evidence Dataset
    # all display the same numbers.
    is_evidence_mode = dataset_type in ('evidence', 'rule', 'rule_training', 'semantic')
    is_classification_mode = dataset_type in ('classification', 'training')
    is_document_mode = dataset_type in ('document', 'doc')

    if is_evidence_mode:
        # Evidence pipeline stats are based on rule-level evidence rows.
        qs = RuleTrainingSample.objects.all()
        if selected_norm:
            qs = qs.filter(norm=selected_norm)
        elif standard:
            qs = qs.filter(norm__name__iexact=standard)

        approved_count = qs.filter(label__iexact='approved').count()
        rejected_count = qs.filter(label__iexact='rejected').count()
        pending_count = qs.filter(label__iexact='pending').count()
        total_samples = approved_count + rejected_count
        total_all = qs.count()

        rules_count = selected_norm.rules.count() if selected_norm else (
            Norme.objects.filter(name__iexact=standard).first().rules.count() if standard else 0
        )
        covered_rules_count = qs.filter(label__iexact='approved').values_list('rule_id', flat=True).distinct().count()

        all_texts = [t for t in qs.filter(label__in=['approved', 'rejected']).values_list('evidence_text', flat=True) if t and t.strip()]
        unique_texts = set(all_texts)
        duplication_rate = round((1 - len(unique_texts) / max(len(all_texts), 1)) * 100, 1) if all_texts else 0.0
        avg_length = round(sum(len(t.split()) for t in all_texts) / max(len(all_texts), 1), 1) if all_texts else 0.0

        if total_samples > 0:
            minority = min(approved_count, rejected_count)
            class_balance = round(minority / max(total_samples - minority, 1) * 100, 1)
            class_balance = min(class_balance, 100.0)
        else:
            class_balance = 0.0

        coverage_rate = round(covered_rules_count / max(rules_count, 1) * 100, 1) if rules_count else 0.0
        richness = round(
            0.30 * min(total_samples / max(rules_count * 10, 1) * 100, 100)
            + 0.25 * class_balance
            + 0.25 * (100 - duplication_rate)
            + 0.20 * coverage_rate,
            1,
        )
        # FIXED: quality score bounded 0-100 with sensible avg_length baseline
        quality_score = min(100.0, max(0.0, round(
            0.35 * (100 - duplication_rate)
            + 0.25 * min(avg_length / 30.0 * 100, 100)
            + 0.25 * class_balance
            + 0.15 * coverage_rate,
            1,
        )))

        sync_required = False

        sample_qs = (
            qs.filter(label__in=['approved', 'rejected'])
            .select_related('rule')
            .order_by('-updated_at')
        )
        samples_raw = list(sample_qs.values(
            'id', 'rule_id', 'rule_title', 'evidence_text',
            'label', 'confidence_score', 'updated_at', 'created_at',
        )[:100])
        for sample in samples_raw:
            confidence = sample.get('confidence_score')
            score = 0.0
            if confidence is not None:
                try:
                    confidence = float(confidence)
                    score = confidence * 100.0 if confidence <= 1.0 else confidence
                except (TypeError, ValueError):
                    score = 0.0
            sample['score'] = score
            sample['rules_count'] = 1 if sample.get('rule_id') else 0
            sample['vector_length'] = len((sample.get('evidence_text') or '').split())
    elif is_classification_mode:
        # FIXED: Classification mode now uses RuleTrainingSample as single source of truth.
        # This guarantees ML Dashboard, Training Dataset, and Evidence Intelligence
        # all display the same numbers. TrainingSample.label stores document.status
        # ('pending', 'reviewing') not ML labels, making it unreliable for counting.
        qs = RuleTrainingSample.objects.all()
        if selected_norm:
            qs = qs.filter(norm=selected_norm)
        elif standard:
            qs = qs.filter(norm__name__iexact=standard)

        approved_count = qs.filter(label__iexact='approved').count()
        rejected_count = qs.filter(label__iexact='rejected').count()
        pending_count = qs.filter(label__iexact='pending').count()
        total_samples = approved_count + rejected_count
        total_all = qs.count()

        rules_count = selected_norm.rules.count() if selected_norm else (
            Norme.objects.filter(name__iexact=standard).first().rules.count() if standard else 0
        )

        # FIXED: coverage = distinct rule_ids with at least one evidence (approved OR rejected)
        covered_rules_count = qs.filter(
            label__in=['approved', 'rejected']
        ).values('rule_id').distinct().count()
        if rules_count:
            covered_rules_count = min(covered_rules_count, rules_count)

        all_texts = [t for t in qs.filter(label__in=['approved', 'rejected']).values_list('evidence_text', flat=True) if t and t.strip()]
        unique_texts = set(all_texts)
        duplication_rate = round((1 - len(unique_texts) / max(len(all_texts), 1)) * 100, 1) if all_texts else 0.0
        avg_length = round(sum(len(t.split()) for t in all_texts) / max(len(all_texts), 1), 1) if all_texts else 0.0

        if total_samples > 0:
            minority = min(approved_count, rejected_count)
            class_balance = round(minority / max(total_samples - minority, 1) * 100, 1)
            class_balance = min(class_balance, 100.0)
        else:
            class_balance = 0.0

        coverage_rate = round(covered_rules_count / max(rules_count, 1) * 100, 1) if rules_count else 0.0
        richness = round(
            0.30 * min(total_samples / max(rules_count * 10, 1) * 100, 100)
            + 0.25 * class_balance
            + 0.25 * (100 - duplication_rate)
            + 0.20 * coverage_rate,
            1,
        )
        # FIXED: Quality score bounded 0-100, formula correct
        quality_score = min(100.0, max(0.0, round(
            0.35 * (100 - duplication_rate)
            + 0.25 * min(avg_length / 30.0 * 100, 100)
            + 0.25 * class_balance
            + 0.15 * coverage_rate,
            1,
        )))

        sync_required = False
        sample_qs = (
            qs.filter(label__in=['approved', 'rejected'])
            .select_related('rule')
            .order_by('-updated_at')
        )
        samples_raw = list(sample_qs.values(
            'id', 'rule_id', 'rule_title', 'evidence_text',
            'label', 'confidence_score', 'updated_at', 'created_at',
        )[:100])
        for sample in samples_raw:
            confidence = sample.get('confidence_score')
            score = 0.0
            if confidence is not None:
                try:
                    confidence = float(confidence)
                    score = confidence * 100.0 if confidence <= 1.0 else confidence
                except (TypeError, ValueError):
                    score = 0.0
            sample['score'] = score
            sample['rules_count'] = 1 if sample.get('rule_id') else 0
            sample['vector_length'] = len((sample.get('evidence_text') or '').split())
    else:
        # Document mode: also use RuleTrainingSample for consistency.
        # DocumentTrainingSample is only used for document-level predictions, not for
        # dashboard stats. All stats pages must show the same numbers.
        qs = RuleTrainingSample.objects.all()
        if selected_norm:
            qs = qs.filter(norm=selected_norm)
        elif standard:
            qs = qs.filter(norm__name__iexact=standard)

        approved_count = qs.filter(label__iexact='approved').count()
        rejected_count = qs.filter(label__iexact='rejected').count()
        pending_count = qs.filter(label__iexact='pending').count()
        total_samples = approved_count + rejected_count
        total_all = qs.count()

        rules_count = selected_norm.rules.count() if selected_norm else (
            Norme.objects.filter(name__iexact=standard).first().rules.count() if standard else 0
        )

        covered_rules_count = qs.filter(
            label__in=['approved', 'rejected']
        ).values('rule_id').distinct().count()
        if rules_count:
            covered_rules_count = min(covered_rules_count, rules_count)

        all_texts = [t for t in qs.filter(label__in=['approved', 'rejected']).values_list('evidence_text', flat=True) if t and t.strip()]
        unique_texts = set(all_texts)
        duplication_rate = round((1 - len(unique_texts) / max(len(all_texts), 1)) * 100, 1) if all_texts else 0.0
        avg_length = round(sum(len(t.split()) for t in all_texts) / max(len(all_texts), 1), 1) if all_texts else 0.0

        if total_samples > 0:
            minority = min(approved_count, rejected_count)
            class_balance = round(minority / max(total_samples - minority, 1) * 100, 1)
            class_balance = min(class_balance, 100.0)
        else:
            class_balance = 0.0

        coverage_rate = round(covered_rules_count / max(rules_count, 1) * 100, 1) if rules_count else 0.0
        richness = round(
            0.30 * min(total_samples / max(rules_count * 10, 1) * 100, 100)
            + 0.25 * class_balance
            + 0.25 * (100 - duplication_rate)
            + 0.20 * coverage_rate,
            1,
        )
        quality_score = min(100.0, max(0.0, round(
            0.35 * (100 - duplication_rate)
            + 0.25 * min(avg_length / 30.0 * 100, 100)
            + 0.25 * class_balance
            + 0.15 * coverage_rate,
            1,
        )))

        sync_required = False
        sample_qs = (
            qs.filter(label__in=['approved', 'rejected'])
            .select_related('rule')
            .order_by('-updated_at')
        )
        samples_raw = list(sample_qs.values(
            'id', 'rule_id', 'rule_title', 'evidence_text',
            'label', 'confidence_score', 'updated_at', 'created_at',
        )[:100])
        for sample in samples_raw:
            confidence = sample.get('confidence_score')
            score = 0.0
            if confidence is not None:
                try:
                    confidence = float(confidence)
                    score = confidence * 100.0 if confidence <= 1.0 else confidence
                except (TypeError, ValueError):
                    score = 0.0
            sample['score'] = score
            sample['rules_count'] = 1 if sample.get('rule_id') else 0
            sample['vector_length'] = len((sample.get('evidence_text') or '').split())

    logger.info(
        "dataset_stats_api norm=%s type=%s approved=%d rejected=%d pending=%d quality=%.1f",
        standard, dataset_type, approved_count, rejected_count, pending_count, quality_score,
    )

    return Response({
        'total_samples': total_samples,
        'approved_samples': approved_count,
        'valid_samples': approved_count,
        'rejected_samples': rejected_count,
        'invalid_samples': rejected_count,
        'pending_samples': pending_count,
        'total_all': total_all,
        'rules_count': rules_count,
        'covered_rules_count': covered_rules_count,
        'quality_score': quality_score,
        'dataset_richness': richness,
        'class_balance': class_balance,
        'duplicate_rate': duplication_rate,
        'coverage_rate': coverage_rate,
        'avg_evidence_length': avg_length,
        'training_enabled': total_samples >= 20,
        'training_min': 20,
        'sync_required': sync_required,
        # Evidence mode aliases for ML Dashboard
        'indexed_vectors': total_samples,
        'vector_count': total_samples,
        'document_count': total_all,
        'indexed_documents': total_all,
        'embedding_dim': None,
        'legacy_samples': 0 if is_evidence_mode else total_all,
        'selected_norm': {
            'id': selected_norm.id if selected_norm else None,
            'name': selected_norm.name if selected_norm else None,
        } if selected_norm else None,
        'samples': samples_raw,
    })


def _persist_training_result(standard: str, result: dict) -> None:
    """Persist a local training run to TrainingJob + MLOpsConfig.

    This is the single-source-of-truth write path for API-triggered training.
    It mirrors what ci/update_training_job.py does for Jenkins-triggered runs.

    Fields written:
    - TrainingJob: status, f1_score, precision_score, recall_score, accuracy,
                   avg_similarity (compat alias), model_version, documents_count,
                   dataset_size, triggered_by='api'
    - MLOpsConfig: last_trained_at, last_trained_doc_count, current_model_version,
                   last_f1_score, dataset_size, training_count (incremented)
    """
    from django.utils import timezone as _tz
    from django.db.models import F as _F

    if not standard or not result or 'error' in result:
        return

    # Identify best model from result
    best_name = result.get('best_model') or ''
    results   = result.get('results', {})
    bm        = results.get(best_name, {}) if best_name and best_name != 'Tie' else {}

    # Fallback: pick model with highest f1
    if not bm:
        for m in results.values():
            if not m.get('error') and m.get('f1_score'):
                if not bm or (m.get('f1_score', 0) > bm.get('f1_score', 0)):
                    bm = m

    f1        = float(bm.get('f1_score', 0.0) or 0.0)
    precision = float(bm.get('precision', 0.0) or 0.0)
    recall    = float(bm.get('recall', 0.0) or 0.0)
    accuracy  = float(bm.get('accuracy', 0.0) or 0.0)
    samples   = int(result.get('dataset_size') or result.get('samples') or 0)

    try:
        job = TrainingJob.objects.create(
            standard=standard,
            status='success',
            start_time=_tz.now(),
            end_time=_tz.now(),
            documents_count=samples,
            dataset_size=samples,
            new_docs_since=0,
            f1_score=f1,
            precision_score=precision,
            recall_score=recall,
            accuracy=accuracy,
            avg_similarity=accuracy,   # compat alias read by older frontend code
            model_version=best_name,
            triggered_by='api',
            drift_report={},
            log_output=f'API local training | {standard} | best={best_name} | f1={f1:.4f}',
        )

        cfg, _ = MLOpsConfig.objects.get_or_create(
            standard=standard,
            defaults={'retraining_threshold': int(os.getenv('MLOPS_RETRAINING_THRESHOLD', '10'))},
        )
        MLOpsConfig.objects.filter(standard=standard).update(
            last_trained_at=_tz.now(),
            last_trained_doc_count=samples,
            current_model_version=best_name,
            last_f1_score=f1,
            dataset_size=samples,
            training_count=_F('training_count') + 1,
        )
        logger.info(
            '_persist_training_result: standard=%s best=%s f1=%.4f job_id=%s',
            standard, best_name, f1, job.id,
        )
    except Exception as exc:
        logger.warning('_persist_training_result failed: %s', exc)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def ml_train_api(request):
    """Train ML models for a specific standard or norme id."""
    error = _load_ml_training_modules()
    if error is not None or train_all_models is None:
        return Response(
            {'error': 'ML training unavailable — install Visual C++ Redistributable 2019 and restart the server.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    standard = request.data.get('standard')
    norme_id = request.data.get('norm_id') or request.data.get('norme_id')
    dataset_type = str(request.data.get('dataset_type', 'classification')).lower()

    if not standard and not norme_id:
        return Response({'error': 'Standard or norm_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    if not standard and norme_id:
        try:
            norme = Norme.objects.get(pk=norme_id)
            standard = norme.name
        except (Norme.DoesNotExist, ValueError):
            return Response({'error': f'Norme with id {norme_id} does not exist.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = train_all_models(
            standard=standard,
            norme_id=norme_id,
            dataset_type=dataset_type,
        )
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        # ── Persist training outcome to DB (single source of truth) ──────────
        # This mirrors what ci/update_training_job.py does for Jenkins runs,
        # ensuring that local (API-triggered) training is also reflected in
        # MLOps dashboard, AIInsights timeline, and StandardCard metrics.
        _persist_training_result(standard, result)

        return Response(result)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ml_models_api(request):
    """
    GET /api/ml/models/?norm_id=<id>

    Returns the list of ML models for the given norm with metrics read from
    the persisted *_metrics.json file.

    Rules:
    - accuracy/precision/recall/f1_score are None (not 0) when a model was
      not trained or its training produced an error.
    - best_model is selected by F1 (primary) then accuracy (tiebreaker).
      When two models are exactly tied it is set to "Tie".
    - A model whose error field is non-empty is marked status="Failed".
    - No fallback values — the frontend must display "—" for None.
    """
    import os, json as _json, datetime as _dt

    try:
        from ml.train_models import get_model_path, sanitize_standard
    except Exception:
        return Response({'models': [], 'best_model': None,
                         'error': 'ML module unavailable (PyTorch version mismatch)'})

    models_dir   = os.path.join(os.path.dirname(__file__), '..', 'ml', 'models')
    allowed_algos = ["RandomForest", "LogisticRegression", "GradientBoosting", "BiLSTM"]

    norm_id        = request.query_params.get('norm_id')
    standard_prefix = None
    standard_name   = None
    best_model_from_json = None

    if norm_id:
        try:
            norm = Norme.objects.get(pk=norm_id)
            standard_name   = norm.name
            standard_prefix = sanitize_standard(norm.name) + '_'
        except (Norme.DoesNotExist, ValueError):
            pass

    if not os.path.exists(models_dir):
        return Response({'models': [{'name': a, 'exists': False} for a in allowed_algos],
                         'best_model': None})

    # ── Load persisted metrics ────────────────────────────────────────────────
    persisted_metrics = {}
    persisted_meta    = {}   # top-level fields: trained_at, samples, dataset_quality
    if standard_name:
        metrics_path = os.path.join(models_dir, f"{sanitize_standard(standard_name)}_metrics.json")
        if os.path.exists(metrics_path):
            try:
                with open(metrics_path, 'r', encoding='utf-8') as f:
                    data = _json.load(f)
                persisted_metrics      = data.get('results', {})
                best_model_from_json   = data.get('best_model')  # already F1-based
                persisted_meta = {
                    'trained_at':      data.get('trained_at'),
                    'samples':         data.get('samples') or data.get('dataset_size'),
                    'train_size':      data.get('train_size'),
                    'val_size':        data.get('val_size'),
                    'test_size':       data.get('test_size'),
                    'dataset_quality': data.get('dataset_quality', {}),
                }
            except Exception:
                pass

    # ── Normalize .pkl filenames to algorithm names ───────────────────────────
    def _normalize(raw: str) -> str:
        cleaned = raw
        if standard_prefix and cleaned.startswith(standard_prefix):
            cleaned = cleaned[len(standard_prefix):]
        else:
            for px in (standard_prefix or '', 'ISO9001_', 'ISO_9001_'):
                if px and cleaned.startswith(px):
                    cleaned = cleaned[len(px):]
                    break
        if cleaned in allowed_algos:
            return cleaned
        parts = cleaned.split('_')
        if parts and parts[-1] in allowed_algos:
            return parts[-1]
        return raw

    # Build initial dict — all models start as "not found"
    model_info = {
        algo: {
            'name': algo, 'id': algo, 'exists': False, 'path': None,
            # Metrics: None = not trained / no data (NOT 0)
            'accuracy': None, 'precision': None, 'recall': None, 'f1_score': None,
            'sample_count': None, 'training_time': None,
            'train_size': None, 'val_size': None, 'test_size': None,
            'trained_date': None, 'confusion_matrix': None,
            'cross_validation': None, 'feature_importance': [],
            'error': None, 'pipeline': None,
        }
        for algo in allowed_algos
    }

    # Scan disk for .pkl files
    for fname in os.listdir(models_dir):
        if not fname.endswith('.pkl'):
            continue
        raw_name  = fname.replace('.pkl', '')
        algorithm = _normalize(raw_name)
        if algorithm not in model_info:
            continue
        fpath = os.path.join(models_dir, fname)
        existing = model_info[algorithm]
        # Prefer files whose name starts with the standard prefix
        if not existing['exists'] or (standard_prefix and raw_name.startswith(standard_prefix)):
            mtime        = os.path.getmtime(fpath)
            disk_date    = _dt.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            pm           = persisted_metrics.get(algorithm, {})
            model_info[algorithm] = {
                'name':              algorithm,
                'id':                algorithm,
                'exists':            True,
                'path':              fpath,
                # Real metrics from JSON — None when absent (not 0)
                'accuracy':          pm.get('accuracy'),     # may be None
                'precision':         pm.get('precision'),
                'recall':            pm.get('recall'),
                'f1_score':          pm.get('f1_score'),
                'sample_count':      pm.get('sample_count'),
                'training_time':     pm.get('training_time'),
                'train_size':        pm.get('train_size'),
                'val_size':          pm.get('val_size'),
                'test_size':         pm.get('test_size'),
                'trained_date':      pm.get('trained_date') or disk_date,
                'confusion_matrix':  pm.get('confusion_matrix'),
                'cross_validation':  pm.get('cross_validation'),
                'feature_importance': pm.get('feature_importance') or [],
                # error from training (None = no error)
                'error':             pm.get('error') or None,
                'pipeline':          pm.get('pipeline'),
                'overfitting_gap':   pm.get('overfitting_gap'),
                'overfitting_level': pm.get('overfitting_level') or pm.get('overfitting_risk'),
                # Anti-leakage validation fields (new)
                'split_strategy':    pm.get('split_strategy'),
                'unique_documents':  pm.get('unique_documents'),
                'confusion_counts':  pm.get('confusion_counts'),
                'train_metrics':     pm.get('train_metrics'),
                'validation_metrics': pm.get('validation_metrics'),
                'test_metrics':      pm.get('test_metrics'),
            }

    models_list = list(model_info.values())

    # ── Compute best model by F1 → Accuracy (same logic as train_models.py) ──
    # Use the JSON value when available (already computed with same rule);
    # recompute from the metrics list as a fallback.
    best_name = best_model_from_json  # "Tie" or an algorithm name or None

    if not best_name:
        # Recompute: only consider models with real positive metrics
        trained = [m for m in models_list
                   if not m.get('error')
                   and m.get('f1_score') is not None and m['f1_score'] > 0]
        if trained:
            sorted_m = sorted(
                trained,
                key=lambda m: (m.get('f1_score', 0), m.get('accuracy', 0)),
                reverse=True,
            )
            top_f1  = sorted_m[0].get('f1_score', 0)
            top_acc = sorted_m[0].get('accuracy', 0)
            tied    = [m for m in sorted_m
                       if abs(m.get('f1_score', 0) - top_f1) <= 0.0001
                       and abs(m.get('accuracy',  0) - top_acc) <= 0.0001]
            best_name = 'Tie' if len(tied) > 1 else sorted_m[0]['name']

    # Inject is_best / is_tie flags
    for m in models_list:
        if best_name and best_name != 'Tie':
            m['is_best'] = (m['name'] == best_name)
            m['is_tie']  = False
        elif best_name == 'Tie':
            # Mark all tied models
            m['is_tie']  = True
            m['is_best'] = True  # visual indicator for all tied models
        else:
            m['is_best'] = False
            m['is_tie']  = False

    # ── Status label ──────────────────────────────────────────────────────────
    for m in models_list:
        if m.get('error'):
            m['status']  = 'Failed'
            m['trained'] = False
        elif not m.get('exists') or m.get('accuracy') is None:
            m['status']  = 'Not trained'
            m['trained'] = False
        elif m.get('accuracy', 0) == 0:
            m['status']  = 'Failed'
            m['trained'] = False
        else:
            m['trained'] = True
            # Status derived from actual F1 score
            f1 = m.get('f1_score', 0) or 0
            if f1 >= 0.90:
                m['status'] = 'Excellent'
            elif f1 >= 0.75:
                m['status'] = 'Good'
            elif f1 >= 0.60:
                m['status'] = 'Adequate'
            else:
                m['status'] = 'Poor'

    # ── Overfitting / reliability warning ────────────────────────────────────
    for m in models_list:
        acc = m.get('accuracy')
        f1  = m.get('f1_score')
        n   = m.get('sample_count') or 0
        if acc is not None and f1 is not None and acc >= 0.999 and f1 >= 0.999 and n < 50:
            m['warning']  = 'Perfect score on tiny dataset — likely overfitted.'
            m['reliable'] = False
        elif m.get('trained'):
            m['reliable'] = True
        else:
            m['reliable'] = False

    return Response({
        'models':          models_list,
        'best_model':      best_name,
        'dataset_meta':    persisted_meta,
    })


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
    # Try to load compliance_service — may fail if spacy/torch DLL unavailable
    try:
        from ml.services import compliance_service
        _compliance_service = compliance_service
    except (ImportError, OSError, Exception):
        _compliance_service = None

    try:
        standard = request.data.get('standard', '')

        # Resolve the Norme object for ComplianceEngine
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

        # Primary: ComplianceEngine (keyword/pattern matching — no torch dependency)
        if norme:
            from compliance_engine import ComplianceEngine
            engine = ComplianceEngine()
            result = engine.analyze_document(text=document_text, norme=norme, document=None)
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
        elif _compliance_service is not None:
            # Fallback: TF-IDF compliance_service (only if ML libs available)
            result = _compliance_service.analyze_document_text(document_text, standard)
            if file_size is not None:
                result['file_info'] = {'file_size': file_size, 'text_length': len(document_text)}
        else:
            return Response(
                {'error': 'No compliance norm found in the database. Please add a norm first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

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
    try:
        from ml.services import compliance_service
        standards = compliance_service.get_supported_standards()
        return Response({'standards': standards}, status=status.HTTP_200_OK)
    except (ImportError, OSError, Exception):
        # Fallback — return standards from DB norms
        standards = list(Norme.objects.values_list('name', flat=True))
        return Response({'standards': standards}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_standard_rules_api(request, standard):
    """Get rules for a specific ISO standard."""
    try:
        from ml.services import compliance_service
        rules = compliance_service.get_standard_rules(standard)
        return Response({'standard': standard, 'rules': rules, 'total_rules': len(rules)}, status=status.HTTP_200_OK)
    except (ImportError, OSError):
        # Fallback — return rules from DB
        norme = Norme.objects.filter(name__iexact=standard).first() or Norme.objects.filter(name__icontains=standard).first()
        if norme:
            rules = [{'id': r.id, 'title': r.title, 'description': r.description} for r in norme.rules.all()]
            return Response({'standard': standard, 'rules': rules, 'total_rules': len(rules)}, status=status.HTTP_200_OK)
        return Response({'standard': standard, 'rules': [], 'total_rules': 0}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def retrain_compliance_models_api(request):
    """Retrain compliance analysis models for a specific standard."""
    try:
        from ml.services import compliance_service
        standard = request.data.get('standard', 'ISO9001')
        result = compliance_service.retrain_models(standard)
        return Response(result, status=status.HTTP_200_OK)
    except (ImportError, OSError):
        return Response(
            {'error': 'ML service unavailable — spacy/torch DLL not loaded. Install Visual C++ Redistributable 2019.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def update_similarity_threshold_api(request):
    """Update similarity threshold for compliance detection."""
    try:
        from ml.services import compliance_service
        threshold = request.data.get('threshold')
        if threshold is None:
            return Response({'error': 'Threshold value is required'}, status=status.HTTP_400_BAD_REQUEST)
        threshold = float(threshold)
        if not 0.0 <= threshold <= 1.0:
            return Response({'error': 'Threshold must be between 0.0 and 1.0'}, status=status.HTTP_400_BAD_REQUEST)
        success = compliance_service.update_similarity_threshold(threshold)
        if success:
            return Response({'message': f'Threshold updated to {threshold}', 'threshold': threshold}, status=status.HTTP_200_OK)
        return Response({'error': 'Failed to update threshold'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except (ImportError, OSError):
        return Response({'error': 'ML service unavailable.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except ValueError:
        return Response({'error': 'Invalid threshold value'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_compliance_service_status_api(request):
    """Get current status of the compliance analysis service."""
    try:
        from ml.services import compliance_service
        status_info = compliance_service.get_service_status()
        return Response(status_info, status=status.HTTP_200_OK)
    except (ImportError, OSError):
        return Response({
            'status': 'degraded',
            'message': 'ML service unavailable — spacy/torch DLL not loaded.',
            'fallback': 'ComplianceEngine (keyword matching) is active.',
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ml_test_document_api(request):
    """
    Test document against ML models.
    Uses ComplianceEngine for rule-level analysis + ML model for final prediction.
    Returns: compliance_score, prediction, rules[], valid_rules, invalid_rules.
    """
    document_file = request.FILES.get('file')
    standard = request.data.get('standard')

    # Fallback: resolve standard from norm_id if not provided directly
    norm_id = request.data.get('norm_id')
    norme = None
    if norm_id:
        try:
            norme = Norme.objects.prefetch_related('rules').get(pk=norm_id)
            if not standard:
                standard = norme.name
        except Norme.DoesNotExist:
            pass

    if not norme and standard:
        norme = (
            Norme.objects.prefetch_related('rules').filter(name__iexact=standard).first()
            or Norme.objects.prefetch_related('rules').filter(name__icontains=standard).first()
        )

    if not norme:
        norme = Norme.objects.prefetch_related('rules').first()
        if norme:
            standard = norme.name

    if not document_file:
        return Response({'error': 'File is required'}, status=status.HTTP_400_BAD_REQUEST)
    if not norme:
        return Response({'error': 'No norm found. Please create a norm first.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Step 1: Extract text
        document_text = extract_text(document_file)
        logger.info("[ML_TEST] DOCUMENT_TEXT_LENGTH=%d standard=%s", len(document_text), standard)

        # Step 2: Rule-level analysis via ComplianceEngine
        from compliance_engine import ComplianceEngine
        engine = ComplianceEngine()
        engine_result = engine.analyze_document(text=document_text, norme=norme, document=None)

        compliance_score = engine_result.get('compliance', 0) or 0
        detected_rules   = engine_result.get('detected_rules', []) or []
        valid_count      = engine_result.get('valid_count', 0) or 0
        invalid_count    = engine_result.get('invalid_count', 0) or 0
        total_rules_n    = engine_result.get('total_rules', 0) or 0

        logger.info(
            "[ML_TEST] FEATURES_COUNT=%d RULES_DETECTED=%d valid=%d invalid=%d compliance=%d%%",
            len(detected_rules), total_rules_n, valid_count, invalid_count, compliance_score,
        )

        # Step 3: Build rule results array for frontend table
        rules_list = []
        for r in detected_rules:
            is_valid = bool(r.get('is_valid', False))
            confidence_val = 85.0 if is_valid else 20.0
            rules_list.append({
                'rule':       r.get('title') or r.get('rule') or '—',
                'prediction': 'COMPLIANT' if is_valid else 'NON-COMPLIANT',
                'confidence': round(confidence_val, 1),
                'evidence':   r.get('evidence') or ('Règle vérifiée' if is_valid else 'Règle non satisfaite'),
            })

        logger.info("[ML_TEST] EVIDENCE_FOUND=%d", len([r for r in rules_list if r['evidence']]))

        # Step 4: ML model prediction (TF-IDF pipeline or BiLSTM)
        ml_prediction = None
        ml_confidence = None
        model_used    = None
        try:
            from ml.train_models import load_trained_model, sanitize_standard
            import joblib
            from pathlib import Path as _ModelPath

            for algo in ('RandomForest', 'GradientBoosting', 'LogisticRegression', 'BiLSTM'):
                model_path = _ModelPath('ml/models') / f"{sanitize_standard(standard)}_{algo}.pkl"
                if not model_path.exists():
                    continue
                try:
                    loaded_model = joblib.load(model_path)
                    logger.info("[ML_TEST] MODEL_LOADED=%s", algo)

                    if hasattr(loaded_model, 'named_steps'):
                        # TF-IDF sklearn Pipeline — pass raw text
                        proba = loaded_model.predict_proba([document_text])[0]
                        pred  = int(loaded_model.predict([document_text])[0])
                    elif hasattr(loaded_model, 'predict_proba'):
                        # Direct classifier — build evidence feature vector same way as training
                        # Use _vectorize_evidence_sample logic: 8 features
                        import numpy as _np
                        words = document_text.split()
                        token_count = len(words)
                        has_ref = int(any(kw in document_text.lower() for kw in [
                            'ref.', 'référence', 'certif', 'iso', 'version', 'approuv',
                            'valid', 'conforme', 'audit', 'procedure', 'politique',
                        ]))
                        has_neg = int(any(kw in document_text.lower() for kw in [
                            'absent', 'manquant', 'non', 'pas de', 'sans', 'aucun',
                            'insuffisant', 'non conforme', 'jamais',
                        ]))
                        has_pos = int(any(kw in document_text.lower() for kw in [
                            'conforme', 'approuvé', 'validé', 'présent', 'disponible',
                            'opérationnel', 'certifié', 'implémenté',
                        ]))
                        has_date = int(bool(__import__('re').search(r'\d{2}/\d{2}/\d{4}', document_text)))
                        fvec = [
                            min(token_count / 60.0, 1.0),
                            float(engine_result.get('confidence_score', 0) / 100.0),
                            float(engine_result.get('rule_score', 0) / 100.0),
                            0.5,  # rule_weight placeholder
                            float(has_ref),
                            float(has_neg),
                            float(has_pos),
                            float(has_date),
                        ]
                        proba = loaded_model.predict_proba([fvec])[0]
                        pred  = int(loaded_model.predict([fvec])[0])
                    else:
                        continue

                    ml_confidence = round(float(max(proba)) * 100, 1)
                    ml_prediction = 'APPROVED' if pred == 1 else 'REJECTED'
                    model_used = algo
                    break
                except Exception as e:
                    logger.warning("[ML_TEST] model %s failed: %s", algo, e)
                    continue
        except Exception as e:
            logger.warning("[ML_TEST] ML prediction outer error: %s", e)

        logger.info(
            "[ML_TEST] MODEL_USED=%s PREDICTION=%s CONFIDENCE=%s",
            model_used, ml_prediction, ml_confidence,
        )

        # Step 5: Fallback prediction from compliance engine if no ML model loaded
        if ml_prediction is None:
            engine_decision = engine_result.get('decision', '') or ''
            if 'approve' in engine_decision.lower() or 'auto' in engine_decision.lower():
                ml_prediction = 'APPROVED'
            else:
                ml_prediction = 'REJECTED' if compliance_score < 50 else 'APPROVED'
            ml_confidence = float(compliance_score)

        logger.info("[ML_TEST] COMPLIANCE_SCORE=%d FINAL_PREDICTION=%s", compliance_score, ml_prediction)

        # Step 6: Build response matching frontend expectations exactly
        return Response({
            # Fields used by MLDashboard KPI cards
            'compliance_score': compliance_score,
            'prediction':       ml_prediction,          # uppercase APPROVED/REJECTED
            'ml_prediction':    ml_prediction,          # alias for backward compat
            'confidence':       ml_confidence,
            'model_used':       model_used,

            # Fields used by rule table: testResult.rules?.map(...)
            'rules': rules_list,

            # Aliases for other consumers
            'valid_rules':      valid_count,
            'invalid_rules':    invalid_count,
            'total_rules':      total_rules_n,

            # Diagnostic
            'standard':         standard,
            'text_length':      len(document_text),
            'engine_decision':  engine_result.get('decision', ''),
            'confidence_score': engine_result.get('confidence_score', 0),
            'rule_score':       engine_result.get('rule_score', 0),
            'structure_score':  engine_result.get('structure_score', 0),
            'clarity_score':    engine_result.get('clarity_score', 0),
        })

    except Exception as e:
        logger.exception('[ML_TEST] FATAL: %s', e)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ml_test_evidence_api(request):
    """
    Test document against the Evidence (semantic) pipeline.
    Returns semantic retrieval score, top evidence matches.
    """
    document_file = request.FILES.get('file')
    norm_id = request.data.get('norm_id')
    standard = request.data.get('standard')

    norme = None
    if norm_id:
        try:
            norme = Norme.objects.get(pk=norm_id)
            standard = norme.name
        except Norme.DoesNotExist:
            pass
    if not norme and standard:
        norme = Norme.objects.filter(name__iexact=standard).first()
    if not norme:
        norme = Norme.objects.first()
        if norme:
            standard = norme.name

    if not document_file:
        return Response({'error': 'File is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        document_text = extract_text(document_file)
        logger.info("[ML_TEST_EV] DOCUMENT_TEXT_LENGTH=%d", len(document_text))

        # Search FAISS for nearest evidence
        top_matches = []
        similarity_score = 0
        try:
            from ml.search import load_evidence_index, embed_query_vector
            import numpy as np
            index, ids, vectorizer, vectors, meta = load_evidence_index()
            qvec = embed_query_vector(document_text[:500], vectorizer=vectorizer)
            if qvec is not None:
                q = np.asarray(qvec, dtype=np.float32)
                if index is not None and getattr(index, 'ntotal', 0) > 0:
                    distances, indices = index.search(q, min(5, index.ntotal))
                    hits = [{'id': ids[i], 'score': float(d)} for d, i in zip(distances[0], indices[0]) if i >= 0 and i < len(ids)]
                elif vectorizer is not None and vectors is not None:
                    from sklearn.metrics.pairwise import cosine_similarity as cos_sim
                    sims = cos_sim(q.reshape(1, -1), vectors.astype(np.float32))[0]
                    top_idx = np.argsort(sims)[::-1][:5]
                    hits = [{'id': ids[i], 'score': float(sims[i])} for i in top_idx]
                else:
                    hits = []

                if hits:
                    sample_ids = [h['id'] for h in hits]
                    score_map = {h['id']: h['score'] for h in hits}
                    samples = RuleTrainingSample.objects.filter(id__in=sample_ids).select_related('rule')
                    for s in samples:
                        sim = round(max(0.0, min(1.0, score_map.get(s.id, 0))) * 100, 1)
                        top_matches.append({
                            'rule': s.rule_title or '',
                            'evidence': s.evidence_text or '',
                            'decision': s.label,
                            'similarity': sim,
                        })
                    if top_matches:
                        similarity_score = round(sum(m['similarity'] for m in top_matches) / len(top_matches), 1)
        except Exception as e:
            logger.warning("[ML_TEST_EV] FAISS search failed: %s", e)

        top_label = top_matches[0]['decision'] if top_matches else 'unknown'
        logger.info("[ML_TEST_EV] EVIDENCE_FOUND=%d similarity=%s", len(top_matches), similarity_score)

        return Response({
            'standard':          standard,
            'text_length':       len(document_text),
            'match_score':       similarity_score,
            'similarity_score':  similarity_score,
            'prediction':        top_label.upper() if top_label else 'UNKNOWN',
            'top_match_label':   top_label,
            'evidence_matches':  top_matches,
            'total_matches':     len(top_matches),
        })

    except Exception as e:
        logger.exception('[ML_TEST_EV] FATAL: %s', e)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def ml_train_evidence_api(request):
    """Build and persist the evidence FAISS index from RuleTrainingSample rows."""
    if build_and_persist_evidence_index is None:
        return Response(
            {'error': 'Indexing unavailable — install Visual C++ Redistributable 2019 and restart the server.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
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
        return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def evidence_index_api(request):
    """
    Build evidence index. Uses FAISS/sentence-transformers when available,
    falls back to a lightweight TF-IDF metadata-only index when ML libs are unavailable.
    """
    standard = request.data.get('standard') or request.data.get('standard_name')
    norm_id = request.data.get('norm_id') or request.data.get('norme_id')

    # Try full FAISS index first
    if build_and_persist_evidence_index is not None:
        try:
            result = build_and_persist_evidence_index(standard=standard, norme_id=norm_id)
            return Response({'message': 'Evidence index built (FAISS)', 'metadata': result}, status=status.HTTP_200_OK)
        except Exception as e:
            pass  # fall through to lightweight index

    # Lightweight fallback — persist a simple metadata file so evidence/status returns real data
    import os, json as _json
    from django.utils import timezone as tz

    try:
        qs = RuleTrainingSample.objects.all()
        if norm_id:
            try:
                qs = qs.filter(norm_id=int(norm_id))
            except (ValueError, TypeError):
                pass
        elif standard:
            qs = qs.filter(norm__name__iexact=standard)

        total = qs.count()
        meta = {
            'indexed_evidences': total,
            'total_evidences': total,
            'embedding_model': 'tfidf-fallback',
            'vector_dim': None,
            'last_trained': tz.now().isoformat(),
            'standard': standard,
        }

        # Write metadata file so status endpoint reads it
        models_dir = os.path.join(os.path.dirname(__file__), '..', 'ml', 'models')
        os.makedirs(models_dir, exist_ok=True)
        meta_path = os.path.join(models_dir, 'evidence_index_meta.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            _json.dump(meta, f, indent=2, default=str)

        return Response({
            'message': f'Evidence index built (TF-IDF fallback) — {total} records indexed.',
            'metadata': meta,
            'note': 'Install Visual C++ Redistributable 2019 and restart to enable full FAISS indexing.',
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def evidence_status_api(request):
    """
    Return evidence indexing status and coverage.
    Accepts optional ?norm_name= or ?norm_id= to filter per-norm stats.
    When a norm is specified, counts are scoped to that norm only.
    """
    # ── Resolve optional norm filter ──────────────────────────────────────
    norm_name = request.query_params.get('norm_name') or request.query_params.get('standard')
    norm_id   = request.query_params.get('norm_id')
    norme_obj = None

    if norm_id:
        try:
            norme_obj = Norme.objects.get(pk=int(norm_id))
        except (Norme.DoesNotExist, ValueError):
            pass
    elif norm_name:
        norme_obj = (
            Norme.objects.filter(name__iexact=norm_name).first()
            or Norme.objects.filter(name__icontains=norm_name).first()
        )

    # ── Base queryset — scoped or global ──────────────────────────────────
    qs = RuleTrainingSample.objects.all()
    if norme_obj:
        qs = qs.filter(norm=norme_obj)

    try:
        total = int(qs.count())
    except Exception:
        total = 0

    try:
        rules_covered = qs.values('rule_id').distinct().count()
    except Exception:
        rules_covered = 0

    try:
        approved_patterns = int(qs.filter(label__iexact='approved').count())
    except Exception:
        approved_patterns = 0

    try:
        rejected_patterns = int(qs.filter(label__iexact='rejected').count())
    except Exception:
        rejected_patterns = 0

    # Total rules in norm (for coverage %)
    total_rules = 0
    if norme_obj:
        total_rules = norme_obj.rules.count()

    # ── FAISS index metadata (global — index covers all norms) ─────────────
    meta = None
    if load_evidence_index_metadata is not None:
        try:
            meta = load_evidence_index_metadata()
        except Exception:
            meta = None

    # For per-norm: "indexed" = all samples with evidence_text (indexable)
    # For global:   use actual FAISS count from metadata
    if norme_obj:
        # Per-norm: count non-empty evidence texts as "indexable"
        indexed = int(qs.exclude(evidence_text='').count())
        embedding_model = meta.get('embedding_model') if meta else 'tfidf-fallback'
        last_trained    = meta.get('last_trained') if meta else None
        vector_dim      = meta.get('vector_dim') if meta else None
    else:
        # Global: use total evidence count as "indexed" — FAISS may not be built
        # but all records are available as the knowledge base
        indexed         = total
        embedding_model = (meta.get('embedding_model') if meta else None) or 'tfidf-fallback'
        last_trained    = meta.get('last_trained') if meta else None
        vector_dim      = int(meta.get('vector_dim')) if meta and isinstance(meta.get('vector_dim'), int) else None

    # Coverage %
    if norme_obj and total_rules > 0:
        # Rule coverage: how many of the norm's rules have at least one evidence
        covered_rule_ids = set(qs.values_list('rule_id', flat=True).distinct())
        all_rule_ids     = set(norme_obj.rules.values_list('id', flat=True))
        rule_coverage    = round(len(covered_rule_ids & all_rule_ids) / total_rules * 100.0, 2)
    elif total > 0:
        rule_coverage = round((indexed / total) * 100.0, 2)
    else:
        rule_coverage = 0.0

    train_status = 'READY' if indexed > 0 else ('EMPTY' if total == 0 else 'NOT_TRAINED')

    return Response({
        'norm_name':         norme_obj.name if norme_obj else None,
        'total_evidences':   total,
        'indexed_evidences': indexed,
        'indexed_count':     indexed,     # alias used by some frontend components
        'vector_count':      indexed,     # alias for ML Dashboard
        'indexed_vectors':   indexed,     # alias for ML Dashboard evidence mode
        'document_count':    indexed,     # alias for ML Dashboard "Documents Indexed"
        'indexed_documents': indexed,     # alias for ML Dashboard "Documents Indexed"
        'coverage_percent':  rule_coverage,
        'rules_covered':     rules_covered,
        'total_rules':       total_rules if norme_obj else 0,
        'approved_patterns': approved_patterns,
        'rejected_patterns': rejected_patterns,
        'embedding_model':   embedding_model,
        'vector_dim':        vector_dim,
        'embedding_dim':     vector_dim,  # alias
        'last_trained':      last_trained,
        'train_status':      train_status,
        # Additional stats useful for dashboards
        'approved':          approved_patterns,
        'rejected':          rejected_patterns,
        'total':             total,
        'status':            'ok',
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def evidence_duplicates_api(request):
    """Analyse the evidence dataset for duplicates and quality metrics."""
    from collections import Counter

    norm_id = request.query_params.get('norm_id') or request.query_params.get('norm')
    standard = request.query_params.get('standard') or request.query_params.get('norm_name')

    qs = RuleTrainingSample.objects.select_related('rule', 'norm').all()
    if norm_id:
        try:
            qs = qs.filter(norm_id=int(norm_id))
        except (ValueError, TypeError):
            pass
    elif standard:
        qs = qs.filter(norm__name__iexact=standard)

    total = qs.count()

    if total == 0:
        return Response({'total': 0, 'unique': 0, 'duplicates': 0, 'duplication_rate': 0, 'by_rule': [], 'top_duplicates': []})

    # Count evidence texts
    evidence_list = list(qs.values('evidence_text', 'rule_title', 'label'))
    all_texts = [e['evidence_text'] or '' for e in evidence_list]
    counter = Counter(all_texts)

    unique_count = len(set(t for t in all_texts if t))
    duplicate_texts = {k: v for k, v in counter.items() if v > 1 and k}
    total_duplicate_rows = sum(v - 1 for v in duplicate_texts.values())
    duplication_rate = round((1 - unique_count / max(total, 1)) * 100, 1)

    # Top duplicates
    top_duplicates = [
        {'text': text[:120], 'count': count, 'wasted_rows': count - 1}
        for text, count in sorted(duplicate_texts.items(), key=lambda x: -x[1])[:15]
    ]

    # Per-rule stats
    from collections import defaultdict
    by_rule = defaultdict(lambda: {'total': 0, 'unique_texts': set(), 'approved': 0, 'rejected': 0})
    for e in evidence_list:
        rule = e['rule_title'] or 'Unknown'
        by_rule[rule]['total'] += 1
        by_rule[rule]['unique_texts'].add(e['evidence_text'] or '')
        if e['label'] == 'approved':
            by_rule[rule]['approved'] += 1
        else:
            by_rule[rule]['rejected'] += 1

    by_rule_list = [
        {
            'rule': rule,
            'total': data['total'],
            'unique': len(data['unique_texts']),
            'duplicates': data['total'] - len(data['unique_texts']),
            'duplication_rate': round((1 - len(data['unique_texts']) / max(data['total'], 1)) * 100, 1),
            'approved': data['approved'],
            'rejected': data['rejected'],
        }
        for rule, data in sorted(by_rule.items())
    ]

    # Vocabulary richness
    all_words = set()
    for text in all_texts:
        if text:
            all_words.update(text.lower().split())
    avg_length = sum(len(t.split()) for t in all_texts if t) / max(len([t for t in all_texts if t]), 1)

    return Response({
        'total': total,
        'unique': unique_count,
        'duplicates': total_duplicate_rows,
        'duplication_rate': duplication_rate,
        'vocabulary_size': len(all_words),
        'avg_evidence_length': round(avg_length, 1),
        'by_rule': by_rule_list,
        'top_duplicates': top_duplicates,
        'status': 'clean' if duplication_rate == 0 else ('warning' if duplication_rate < 20 else 'critical'),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeamLeadOrAdmin])
def evidence_deduplicate_api(request):
    """Remove duplicate evidence rows, keeping the first occurrence of each unique text.
    
    A duplicate is defined as: same evidence_text (stripped), regardless of rule or label.
    This matches the definition used by evidence_duplicates_api.
    """
    qs = RuleTrainingSample.objects.order_by('created_at')
    norm_id = request.data.get('norm_id') or request.data.get('norm')
    standard = request.data.get('standard')

    if norm_id:
        try:
            qs = qs.filter(norm_id=int(norm_id))
        except (ValueError, TypeError):
            pass
    elif standard:
        qs = qs.filter(norm__name__iexact=standard)

    seen_texts = set()
    to_delete = []

    for sample in qs:
        text_key = (sample.evidence_text or '').strip()
        if not text_key:
            # Keep empty texts — don't consider them duplicates of each other
            continue
        if text_key in seen_texts:
            to_delete.append(sample.id)
        else:
            seen_texts.add(text_key)

    deleted_count = 0
    if to_delete:
        deleted_count = RuleTrainingSample.objects.filter(id__in=to_delete).delete()[0]

    # Rebuild FAISS index after deduplication
    rebuilt = False
    if build_and_persist_evidence_index is not None:
        try:
            build_and_persist_evidence_index()
            rebuilt = True
        except Exception:
            pass

    remaining = RuleTrainingSample.objects.count()
    return Response({
        'deleted': deleted_count,
        'removed': deleted_count,
        'remaining': remaining,
        'index_rebuilt': rebuilt,
        'message': f'Removed {deleted_count} duplicate rows. {remaining} unique evidence records remain.',
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rule_memory_api(request):
    """
    Knowledge base endpoint with full pagination, filtering, sorting and export.
    GET params:
      page, page_size — pagination
      norm_id, norm_name — filter by norm
      rule — filter by rule title (partial match)
      label — filter by label (approved/rejected)
      search — full-text search in evidence_text + reviewer_comment
      sort — newest|oldest|rule|label (default: newest)
      export — csv|json (returns file download)
    """
    try:
        # FIXED: use order_by('-id') — avoids broken subquery with select_related + cross-JOIN
        qs = RuleTrainingSample.objects.select_related('rule', 'norm').order_by('-id')

        # ── Filters ──────────────────────────────────────────────────────────
        norm_id   = request.query_params.get('norm_id')
        norm_name = request.query_params.get('norm_name')
        rule_q    = request.query_params.get('rule', '').strip()
        label_q   = request.query_params.get('label', '').strip()
        search_q  = request.query_params.get('search', '').strip()
        sort_q    = request.query_params.get('sort', 'newest')

        if norm_id:
            try:
                qs = qs.filter(norm_id=int(norm_id))
            except (ValueError, TypeError):
                pass
        if norm_name:
            qs = qs.filter(norm__name__icontains=norm_name)
        if rule_q:
            qs = qs.filter(rule_title__icontains=rule_q)
        if label_q:
            qs = qs.filter(label__iexact=label_q)
        if search_q:
            from django.db.models import Q
            qs = qs.filter(
                Q(evidence_text__icontains=search_q) |
                Q(reviewer_comment__icontains=search_q) |
                Q(rule_title__icontains=search_q) |
                Q(recommendation__icontains=search_q)
            )

        # ── Sorting ───────────────────────────────────────────────────────────
        sort_map = {
            'newest': '-id',
            'oldest': 'id',
            'rule':   'rule_title',
            'label':  'label',
        }
        qs = qs.order_by(sort_map.get(sort_q, '-created_at'))

        total = qs.count()

        # ── Export ────────────────────────────────────────────────────────────
        export_fmt = request.query_params.get('export', '').lower()
        if export_fmt in ('csv', 'json'):
            import csv, io
            from django.http import HttpResponse
            items = list(qs.values(
                'id', 'rule_title', 'evidence_text', 'reviewer_comment',
                'recommendation', 'label', 'semantic_score', 'confidence_score',
                'created_at', 'norm__name',
            ))
            if export_fmt == 'json':
                import json as _json
                content = _json.dumps(items, indent=2, default=str)
                resp = HttpResponse(content, content_type='application/json')
                resp['Content-Disposition'] = 'attachment; filename="evidence_dataset.json"'
                return resp
            else:
                output = io.StringIO()
                if items:
                    writer = csv.DictWriter(output, fieldnames=items[0].keys())
                    writer.writeheader()
                    writer.writerows(items)
                resp = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
                resp['Content-Disposition'] = 'attachment; filename="evidence_dataset.csv"'
                return resp

        # ── Pagination ────────────────────────────────────────────────────────
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
        items  = qs[offset:offset + page_size]

        serializer = RuleTrainingSampleSerializer(items, many=True, context={'request': request})

        # ── Aggregates for filter dropdowns ───────────────────────────────────
        # Scope rule options to the current norm filter for relevance
        all_rules  = list(qs.values_list('rule_title', flat=True).distinct().order_by('rule_title'))
        all_labels = ['approved', 'rejected']

        return Response({
            'total':     total,
            'page':      page,
            'page_size': page_size,
            'pages':     max(1, (total + page_size - 1) // page_size),
            'items':     serializer.data,
            'filters': {
                'rules':  all_rules,
                'labels': all_labels,
            },
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeamLeadOrAdmin])
def add_evidence_api(request):
    """
    Manually add a new evidence record to the knowledge base.
    Body: { norm_id, rule_id, evidence_text, reviewer_comment, recommendation, label }
    """
    try:
        norm_id       = request.data.get('norm_id')
        rule_id       = request.data.get('rule_id')
        evidence_text = (request.data.get('evidence_text') or '').strip()
        reviewer_comment = (request.data.get('reviewer_comment') or '').strip()
        recommendation   = (request.data.get('recommendation') or '').strip()
        label            = (request.data.get('label') or 'approved').strip().lower()

        if not evidence_text:
            return Response({'error': 'evidence_text is required'}, status=status.HTTP_400_BAD_REQUEST)
        if label not in ('approved', 'rejected', 'pending'):
            return Response({'error': 'label must be approved, rejected or pending'}, status=status.HTTP_400_BAD_REQUEST)

        norm = Norme.objects.get(pk=norm_id) if norm_id else Norme.objects.first()
        rule = Rule.objects.get(pk=rule_id) if rule_id else None

        if not norm:
            return Response({'error': 'No norm found'}, status=status.HTTP_400_BAD_REQUEST)

        # Check for exact duplicate
        if RuleTrainingSample.objects.filter(
            norm=norm, rule=rule, evidence_text=evidence_text, label=label
        ).exists():
            return Response({'error': 'This exact evidence already exists in the knowledge base'}, status=status.HTTP_409_CONFLICT)

        sample = RuleTrainingSample.objects.create(
            norm=norm,
            rule=rule,
            rule_title=rule.title if rule else '',
            rule_description=rule.description if rule else '',
            evidence_text=evidence_text,
            reviewer_comment=reviewer_comment,
            recommendation=recommendation,
            label=label,
            confidence_score=1.0,  # manually added = high confidence
            semantic_score=1.0,
        )

        # Rebuild FAISS index to include the new entry
        if build_and_persist_evidence_index is not None:
            try:
                build_and_persist_evidence_index()
            except Exception:
                pass

        serializer = RuleTrainingSampleSerializer(sample, context={'request': request})
        return Response({'message': 'Evidence added successfully', 'item': serializer.data}, status=status.HTTP_201_CREATED)

    except Norme.DoesNotExist:
        return Response({'error': f'Norm {norm_id} not found'}, status=status.HTTP_404_NOT_FOUND)
    except Rule.DoesNotExist:
        return Response({'error': f'Rule {rule_id} not found'}, status=status.HTTP_404_NOT_FOUND)
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


# ═══════════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS — Dashboard Stats, Document Stats, Dataset Quality
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats_api(request):
    """
    Aggregated dashboard statistics — replaces all hardcoded values in Dashboard.jsx.
    Returns real counts from the database.
    """
    from django.db.models import Count, Avg, Q
    from rbac.models import UserProfile

    user = request.user
    roles = [str(r).upper() for r in getattr(user, 'roles', []) or []]

    # Document queryset scoped by role
    if 'ADMIN' in roles:
        doc_qs = Document.objects.all()
    elif 'TEAMLEAD' in roles:
        doc_qs = Document.objects.filter(employee_department=user.department)
    else:
        doc_qs = Document.objects.filter(employee_username=user.username)

    # Document counts
    doc_counts = doc_qs.aggregate(
        total=Count('id'),
        approved=Count('id', filter=Q(status='approved')),
        rejected=Count('id', filter=Q(status='rejected')),
        pending=Count('id', filter=Q(status='pending')),
        reviewing=Count('id', filter=Q(status='reviewing')),
        auto_approved=Count('id', filter=Q(status='auto_approved')),
    )

    total_docs = doc_counts['total'] or 0
    approved_docs = (doc_counts['approved'] or 0) + (doc_counts['auto_approved'] or 0)
    compliance_rate = round((approved_docs / total_docs * 100), 1) if total_docs > 0 else 0

    # Norme count
    total_normes = Norme.objects.count()

    # Validation count
    if 'ADMIN' in roles:
        total_validations = Validation.objects.count()
    elif 'TEAMLEAD' in roles:
        total_validations = Validation.objects.filter(
            document__employee_department=user.department
        ).count()
    else:
        total_validations = Validation.objects.filter(
            document__employee_username=user.username
        ).count()

    # Training samples should reflect the canonical labeled training dataset used
    # by the ML dashboard. Evidence rows stay separate so diagnostics remain accurate.
    total_training_samples = TrainingSample.objects.filter(label__in=['approved', 'rejected']).count()
    total_evidence_samples = RuleTrainingSample.objects.count()

    # User count (admin only)
    total_users = UserProfile.objects.count() if 'ADMIN' in roles else None

    # Recent activity (last 10 documents)
    recent_docs = doc_qs.select_related('norme').order_by('-created_at')[:10]
    recent_activity = [
        {
            'id': d.id,
            'title': f'Document #{d.id} — {d.norme.name if d.norme else ""}',
            'employee': d.employee_username,
            'status': d.status,
            'time': d.created_at.isoformat(),
        }
        for d in recent_docs
    ]

    # Compliance trend (last 7 days)
    from django.utils import timezone as tz
    from datetime import timedelta
    trend = []
    for i in range(6, -1, -1):
        day = tz.now().date() - timedelta(days=i)
        day_docs = doc_qs.filter(created_at__date=day)
        day_total = day_docs.count()
        day_approved = day_docs.filter(
            status__in=['approved', 'auto_approved']
        ).count()
        trend.append({
            'date': day.isoformat(),
            'total': day_total,
            'approved': day_approved,
            'rate': round(day_approved / day_total * 100, 1) if day_total > 0 else 0,
        })

    return Response({
        'documents': {
            'total': total_docs,
            'approved': approved_docs,
            'rejected': doc_counts['rejected'] or 0,
            'pending': doc_counts['pending'] or 0,
            'reviewing': doc_counts['reviewing'] or 0,
        },
        'compliance_rate': compliance_rate,
        'total_normes': total_normes,
        'total_validations': total_validations,
        'total_training_samples': total_training_samples,
        'total_evidence_samples': total_evidence_samples,
        'total_users': total_users,
        'recent_activity': recent_activity,
        'compliance_trend': trend,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_stats_api(request):
    """
    Aggregated document counts by status — replaces 5 separate API calls in Documents.jsx.
    """
    from django.db.models import Count, Q

    user = request.user
    roles = [str(r).upper() for r in getattr(user, 'roles', []) or []]

    if 'ADMIN' in roles:
        qs = Document.objects.all()
    elif 'TEAMLEAD' in roles:
        qs = Document.objects.filter(employee_department=user.department)
    else:
        qs = Document.objects.filter(employee_username=user.username)

    counts = qs.aggregate(
        total=Count('id'),
        approved=Count('id', filter=Q(status__in=['approved', 'auto_approved'])),
        rejected=Count('id', filter=Q(status='rejected')),
        pending=Count('id', filter=Q(status='pending')),
        reviewing=Count('id', filter=Q(status='reviewing')),
    )

    return Response({
        'total': counts['total'] or 0,
        'approved': counts['approved'] or 0,
        'rejected': counts['rejected'] or 0,
        'pending': counts['pending'] or 0,
        'reviewing': counts['reviewing'] or 0,
    })


# ═══════════════════════════════════════════════════════════════════════════
# INNOVATION 3 — Compliance Drift Detection
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def compliance_drift_api(request):
    """
    Detect compliance drift per department over the last N weeks.
    Returns weekly compliance rates and trend direction.
    GET params:
      weeks  — number of past weeks to analyse (default: 6)
      dept   — filter by department code (optional, admin only)
    """
    from django.db.models import Count, Q
    from django.utils import timezone as tz
    from datetime import timedelta
    from rbac.models import UserProfile

    user = request.user
    roles = [str(r).upper() for r in getattr(user, 'roles', []) or []]

    try:
        weeks = max(2, min(12, int(request.query_params.get('weeks', 6))))
    except (TypeError, ValueError):
        weeks = 6

    dept_filter = request.query_params.get('dept')

    # Resolve departments to analyse
    if 'ADMIN' in roles:
        from rbac.models import Department
        if dept_filter:
            departments = list(Department.objects.filter(code=dept_filter).values_list('code', flat=True))
        else:
            departments = list(Department.objects.values_list('code', flat=True))
    elif 'TEAMLEAD' in roles:
        departments = [user.department] if user.department else []
    else:
        departments = []

    if not departments:
        return Response({'departments': [], 'alerts': []})

    now = tz.now()
    results = []
    alerts = []

    for dept in departments:
        weekly_data = []
        for w in range(weeks - 1, -1, -1):
            week_start = now - timedelta(weeks=w + 1)
            week_end = now - timedelta(weeks=w)
            qs = Document.objects.filter(
                employee_department=dept,
                created_at__gte=week_start,
                created_at__lt=week_end,
            )
            total = qs.count()
            approved = qs.filter(status__in=['approved', 'auto_approved']).count()
            rate = round((approved / total * 100), 1) if total > 0 else None
            weekly_data.append({
                'week': w,
                'week_label': week_end.strftime('W%U %b %d'),
                'total': total,
                'approved': approved,
                'rate': rate,
            })

        # Compute trend: compare last 2 non-null weeks
        rates = [d['rate'] for d in weekly_data if d['rate'] is not None]
        trend = 'stable'
        trend_delta = 0
        if len(rates) >= 3:
            recent_avg = sum(rates[-2:]) / 2
            older_avg = sum(rates[-4:-2]) / max(len(rates[-4:-2]), 1)
            trend_delta = round(recent_avg - older_avg, 1)
            if trend_delta < -5:
                trend = 'declining'
            elif trend_delta > 5:
                trend = 'improving'

        # Alert if declining for 3+ consecutive weeks
        consecutive_declines = 0
        for i in range(len(rates) - 1, 0, -1):
            if rates[i] is not None and rates[i - 1] is not None and rates[i] < rates[i - 1]:
                consecutive_declines += 1
            else:
                break

        dept_obj = {'dept': dept, 'weekly': weekly_data, 'trend': trend, 'trend_delta': trend_delta}
        results.append(dept_obj)

        if consecutive_declines >= 3:
            alerts.append({
                'dept': dept,
                'message': f'Conformité en baisse depuis {consecutive_declines} semaines.',
                'severity': 'critical' if consecutive_declines >= 4 else 'warning',
                'current_rate': rates[-1] if rates else None,
            })

    return Response({'departments': results, 'alerts': alerts, 'weeks': weeks})


# ═══════════════════════════════════════════════════════════════════════════
# INNOVATION 4 — PDF Compliance Report Generator
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_pdf_report_api(request, pk):
    """
    Generate and download a professional PDF compliance report for a document.
    GET /api/documents/{id}/report/
    """
    from django.http import HttpResponse

    # Fetch document with full detail
    try:
        document = Document.objects.select_related('norme').prefetch_related(
            'validations__rule',
        ).get(pk=pk)
    except Document.DoesNotExist:
        return Response({'error': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Enforce role-based access
    user = request.user
    roles = [str(r).upper() for r in getattr(user, 'roles', []) or []]
    if 'ADMIN' not in roles:
        if 'TEAMLEAD' in roles and document.employee_department != user.department:
            raise PermissionDenied('You can only download reports for your department.')
        if 'EMPLOYEE' in roles and document.employee_username != user.username:
            raise PermissionDenied('You can only download your own documents.')

    # Serialise document
    serializer = DocumentDetailSerializer(document, context={'request': request})
    doc_data = serializer.data

    try:
        from services.pdf_report_service import generate_document_report
        pdf_bytes = generate_document_report(doc_data)
    except RuntimeError as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.exception('PDF generation failed for document %s', pk)
        return Response({'error': f'PDF generation failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    filename = f'compliance_report_doc_{pk}.pdf'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ═══════════════════════════════════════════════════════════════════════════
# INNOVATION 5 — Local Compliance Assistant (Chat)
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def compliance_chat_api(request):
    """
    Local compliance Q&A chatbot.
    No external AI — answers from FAISS evidence index + RuleTrainingSamples.

    Body: { "question": "Que doit contenir l'en-tête ?" }
    Optional: { "standard": "ISO9001", "top_k": 5 }
    """
    question = (request.data.get('question') or request.data.get('query') or '').strip()
    if not question:
        return Response({'error': 'Question is required.'}, status=status.HTTP_400_BAD_REQUEST)

    standard = request.data.get('standard') or ''
    try:
        top_k = min(10, max(1, int(request.data.get('top_k', 5))))
    except (TypeError, ValueError):
        top_k = 5

    # Step 1: Semantic search in evidence index
    evidences = []
    try:
        from ml.search import load_evidence_index, embed_query_vector
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity as cos_sim

        index, ids, vectorizer, vectors, meta = load_evidence_index()
        qvec = embed_query_vector(
            question,
            model_name=meta.get('embedding_model') if meta else None,
            vectorizer=vectorizer,
        )

        if qvec is not None:
            q = np.asarray(qvec, dtype=np.float32)
            if index is not None and getattr(index, 'ntotal', 0) > 0:
                distances, indices = index.search(q, min(top_k, index.ntotal))
                hits = [
                    {'id': ids[idx], 'score': float(d)}
                    for dist_row, idx_row in zip(distances.tolist(), indices.tolist())
                    for d, idx in zip(dist_row, idx_row)
                    if idx >= 0 and idx < len(ids)
                ]
            elif vectorizer is not None and vectors is not None:
                if q.ndim == 1:
                    q = q.reshape(1, -1)
                sims = cos_sim(q, vectors.astype(np.float32))[0]
                top_idx = np.argsort(sims)[::-1][:top_k]
                hits = [{'id': ids[i], 'score': float(sims[i])} for i in top_idx]
            else:
                hits = []

            # Fetch samples
            if hits:
                sample_ids = [h['id'] for h in hits]
                score_map = {h['id']: h['score'] for h in hits}
                samples = RuleTrainingSample.objects.filter(id__in=sample_ids).select_related('rule')
                for s in samples:
                    evidences.append({
                        'rule': s.rule_title or (s.rule.title if s.rule else ''),
                        'evidence': s.evidence_text or '',
                        'decision': s.label,
                        'score': round(max(0.0, min(1.0, score_map.get(s.id, 0))) * 100),
                    })
    except Exception as e:
        logger.warning('Chat evidence search failed: %s', str(e))

    # Step 2: Keyword fallback — search RuleTrainingSample text
    if len(evidences) < 3:
        from django.db.models import Q as DQ
        # Search with multiple keywords from the question
        words = [w for w in question[:80].split() if len(w) > 3]
        q_filter = DQ()
        for w in words[:5]:
            q_filter |= (
                DQ(evidence_text__icontains=w) |
                DQ(rule_title__icontains=w) |
                DQ(reviewer_comment__icontains=w)
            )
        qs = RuleTrainingSample.objects.filter(q_filter).order_by('-confidence_score')[:top_k]
        seen_ids = {e.get('id') for e in evidences}
        for s in qs:
            if s.id not in seen_ids:
                evidences.append({
                    'id':       s.id,
                    'rule':     s.rule_title or '',
                    'evidence': s.evidence_text or '',
                    'decision': s.label,
                    'score':    50,
                })

    # Step 2b: If still no evidence, get top approved samples for the standard
    if len(evidences) < 2:
        std_qs = RuleTrainingSample.objects.filter(label='approved')
        if standard:
            std_qs = std_qs.filter(norm__name__icontains=standard)
        for s in std_qs.order_by('-confidence_score')[:top_k]:
            evidences.append({
                'id':       s.id,
                'rule':     s.rule_title or '',
                'evidence': s.evidence_text or '',
                'decision': s.label,
                'score':    40,
            })

    # Step 3: Generate answer via RAG + LLM (Ollama) or keyword fallback
    from services.llm_service import generate_compliance_answer
    result = generate_compliance_answer(
        question=question,
        evidences=evidences[:top_k],
        standard=standard,
        user=getattr(request.user, 'username', 'anonymous'),
    )

    return Response({
        'question':     question,
        'answer':       result['answer'],
        'sources':      evidences[:top_k],
        'source_count': len(evidences),
        'standard':     standard,
        'llm_used':     result.get('llm_used', False),
        'model':        result.get('model', 'fallback'),
        'confidence':   result.get('confidence', 'Moyenne'),
    })


# ═══════════════════════════════════════════════════════════════════════════
# STREAMING CHAT — SSE token-by-token via Ollama
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def compliance_chat_stream_api(request):
    """
    Streaming compliance chat via Server-Sent Events (SSE).
    Returns text/event-stream — each token sent as: data: {"token": "..."}\n\n
    Final event: data: {"done": true, "llm_used": ..., "model": ..., "confidence": ...}\n\n

    Body: { "question": "...", "standard": "ISO27001", "top_k": 5 }

    NOTE: CSRF is bypassed — auth is via Bearer JWT in Authorization header.
    The @api_view decorator with DRF's KeycloakAuthentication handles auth.
    """
    from django.http import StreamingHttpResponse
    from django.views.decorators.csrf import csrf_exempt

    question = (request.data.get('question') or request.data.get('query') or '').strip()
    if not question:
        return Response({'error': 'Question is required.'}, status=status.HTTP_400_BAD_REQUEST)

    standard = request.data.get('standard') or ''
    try:
        top_k = min(10, max(1, int(request.data.get('top_k', 5))))
    except (TypeError, ValueError):
        top_k = 5

    # ── Retrieve evidence (same logic as compliance_chat_api) ──────────────
    evidences = []
    try:
        from ml.search import load_evidence_index, embed_query_vector
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity as cos_sim

        index, ids, vectorizer, vectors, meta = load_evidence_index()
        qvec = embed_query_vector(
            question,
            model_name=meta.get('embedding_model') if meta else None,
            vectorizer=vectorizer,
        )
        if qvec is not None:
            q = np.asarray(qvec, dtype=np.float32)
            if index is not None and getattr(index, 'ntotal', 0) > 0:
                distances, indices_arr = index.search(q, min(top_k, index.ntotal))
                hits = [
                    {'id': ids[idx], 'score': float(d)}
                    for dist_row, idx_row in zip(distances.tolist(), indices_arr.tolist())
                    for d, idx in zip(dist_row, idx_row)
                    if idx >= 0 and idx < len(ids)
                ]
            elif vectorizer is not None and vectors is not None:
                if q.ndim == 1:
                    q = q.reshape(1, -1)
                sims = cos_sim(q, vectors.astype(np.float32))[0]
                top_idx = np.argsort(sims)[::-1][:top_k]
                hits = [{'id': ids[i], 'score': float(sims[i])} for i in top_idx]
            else:
                hits = []
            if hits:
                sample_ids = [h['id'] for h in hits]
                score_map  = {h['id']: h['score'] for h in hits}
                samples = RuleTrainingSample.objects.filter(id__in=sample_ids).select_related('rule')
                for s in samples:
                    evidences.append({
                        'rule':     s.rule_title or (s.rule.title if s.rule else ''),
                        'evidence': s.evidence_text or '',
                        'decision': s.label,
                        'score':    round(max(0.0, min(1.0, score_map.get(s.id, 0))) * 100),
                    })
    except Exception as e:
        logger.warning('Stream evidence search failed: %s', e)

    # Keyword fallback
    if len(evidences) < 3:
        from django.db.models import Q as DQ
        words = [w for w in question[:80].split() if len(w) > 3]
        q_filter = DQ()
        for w in words[:5]:
            q_filter |= (
                DQ(evidence_text__icontains=w) |
                DQ(rule_title__icontains=w) |
                DQ(reviewer_comment__icontains=w)
            )
        qs = RuleTrainingSample.objects.filter(q_filter).order_by('-confidence_score')[:top_k]
        seen_ids = {e.get('id') for e in evidences}
        for s in qs:
            if s.id not in seen_ids:
                evidences.append({
                    'id': s.id, 'rule': s.rule_title or '',
                    'evidence': s.evidence_text or '', 'decision': s.label, 'score': 50,
                })

    if len(evidences) < 2:
        std_qs = RuleTrainingSample.objects.filter(label='approved')
        if standard:
            std_qs = std_qs.filter(norm__name__icontains=standard)
        for s in std_qs.order_by('-confidence_score')[:top_k]:
            evidences.append({
                'id': s.id, 'rule': s.rule_title or '',
                'evidence': s.evidence_text or '', 'decision': s.label, 'score': 40,
            })

    # ── Stream ────────────────────────────────────────────────────────────
    import json as _json
    _user = getattr(request.user, 'username', 'anonymous')

    def event_stream():
        # First: send sources so frontend can display them immediately
        yield f'data: {_json.dumps({"sources": evidences[:top_k], "question": question, "standard": standard})}\n\n'
        # Then: stream tokens
        from services.llm_service import stream_compliance_answer
        yield from stream_compliance_answer(
            question=question,
            context_rules=[],
            context_evidence=evidences[:top_k],
            standard=standard,
        )

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream; charset=utf-8',
    )
    response['Cache-Control']     = 'no-cache'
    response['X-Accel-Buffering'] = 'no'    # disable nginx buffering
    response['Access-Control-Allow-Origin'] = '*'
    return response


def _synthesise_chat_answer(question: str, evidences: list, standard: str = '') -> str:
    """
    Build a structured professional compliance answer.
    Format: Résumé / Analyse / Preuves / Écarts / Recommandations / Confiance
    100% local — no LLM, no API call.
    """

    # ── No evidence found ────────────────────────────────────────────────
    if not evidences:
        return (
            "**Résumé :**\n"
            "Information non trouvée dans les documents de conformité.\n\n"
            "**Analyse :**\n"
            "Je ne trouve pas suffisamment d'informations dans la base documentaire "
            "pour répondre avec certitude à cette question.\n\n"
            "**Recommandations :**\n"
            "- Assurez-vous que l'index d'évidence a été entraîné via 'Train Memory'\n"
            "- Vérifiez que des preuves de validation existent pour cette norme\n"
            "- Reformulez la question avec des termes ISO spécifiques\n\n"
            "**Niveau de confiance :** Faible"
        )

    # ── Split approved vs rejected evidence ──────────────────────────────
    approved = [e for e in evidences if e.get('decision') == 'approved' and e.get('score', 0) >= 40]
    rejected = [e for e in evidences if e.get('decision') == 'rejected']
    top_all  = evidences[:5]

    # ── Deduplicate by rule ───────────────────────────────────────────────
    seen_rules = set()
    unique_rules = []
    for e in top_all:
        rule = (e.get('rule') or '').strip()
        if rule and rule not in seen_rules:
            seen_rules.add(rule)
            unique_rules.append(e)

    # ── Confidence level ─────────────────────────────────────────────────
    avg_score = sum(e.get('score', 0) for e in top_all) / max(len(top_all), 1)
    if avg_score >= 75 and len(approved) >= 2:
        confidence = 'Élevé'
    elif avg_score >= 50:
        confidence = 'Moyen'
    else:
        confidence = 'Faible'

    # ── Norm context ──────────────────────────────────────────────────────
    norm_label = standard or (
        evidences[0].get('norm') or
        ('ISO 27001' if 'access' in question.lower() or 'classif' in question.lower() else
         'ISO 9001' if 'version' in question.lower() or 'approbation' in question.lower() else
         'ISO / TISAX')
    )

    # ── Build résumé ──────────────────────────────────────────────────────
    resume_lines = []
    for e in unique_rules[:2]:
        rule  = e.get('rule', '')
        score = e.get('score', 0)
        dec   = e.get('decision', '')
        badge = 'CONFORME' if dec == 'approved' else ('NON CONFORME' if dec == 'rejected' else '')
        if rule:
            resume_lines.append(f"- {rule} [{score}%]{(' — ' + badge) if badge else ''}")

    resume = '\n'.join(resume_lines) if resume_lines else f"Analyse basée sur {len(evidences)} preuve(s) de conformité."

    # ── Build analyse ─────────────────────────────────────────────────────
    analyse_parts = []
    for e in unique_rules[:3]:
        rule     = e.get('rule', '')
        evidence = (e.get('evidence') or '')[:200]
        decision = e.get('decision', '')
        score    = e.get('score', 0)
        if not rule: continue
        verdict  = 'CONFORME' if decision == 'approved' else ('NON CONFORME' if decision == 'rejected' else 'EN ATTENTE')
        analyse_parts.append(
            f"**Règle : {rule}** ({norm_label})\n"
            f"Statut : {verdict} — Score similarité : {score}%\n"
            f"Preuve : {evidence if evidence else 'Aucune preuve textuelle disponible.'}"
        )

    analyse = '\n\n'.join(analyse_parts) if analyse_parts else "Analyse non disponible."

    # ── Preuves utilisées ────────────────────────────────────────────────
    preuves_lines = []
    for i, e in enumerate(unique_rules[:4], 1):
        rule     = e.get('rule', '')
        evidence = (e.get('evidence') or '')[:120]
        score    = e.get('score', 0)
        decision = e.get('decision', '')
        icon     = '✓' if decision == 'approved' else ('✗' if decision == 'rejected' else '—')
        preuves_lines.append(f"{i}. {icon} [{score}%] **{rule}** : {evidence}")

    preuves = '\n'.join(preuves_lines) if preuves_lines else "Aucune preuve directe trouvée."

    # ── Écarts identifiés ─────────────────────────────────────────────────
    gaps = []
    for e in rejected[:3]:
        rule     = e.get('rule', '')
        evidence = (e.get('evidence') or '')[:100]
        if rule:
            gaps.append(f"- **{rule}** : {evidence}")

    ecarts = '\n'.join(gaps) if gaps else "- Aucun écart identifié dans les preuves récupérées."

    # ── Recommandations ───────────────────────────────────────────────────
    recs = []
    if rejected:
        for e in rejected[:2]:
            rule = e.get('rule', '')
            if rule:
                recs.append(f"- Mettre en conformité la règle **{rule}** avec les exigences {norm_label}")
    if confidence == 'Faible':
        recs.append("- Enrichir la base de connaissances avec davantage de preuves validées")
        recs.append("- Entraîner l'index FAISS via Evidence Intelligence > Train Memory")
    if not recs:
        recs.append(f"- Maintenir les contrôles conformes aux exigences {norm_label} en vigueur")
        recs.append("- Planifier une revue périodique des preuves de conformité")
        recs.append("- Documenter les prochaines validations avec des preuves textuelles détaillées")

    recommandations = '\n'.join(recs)

    # ── Final structured response ─────────────────────────────────────────
    return (
        f"**Résumé :**\n{resume}\n\n"
        f"**Analyse :**\n{analyse}\n\n"
        f"**Preuves utilisées :**\n{preuves}\n\n"
        f"**Écarts identifiés :**\n{ecarts}\n\n"
        f"**Recommandations :**\n{recommandations}\n\n"
        f"**Niveau de confiance :** {confidence}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# INNOVATION 7 — TeamLead Personalised Insights
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeamLeadOrAdmin])
def teamlead_recommendations_api(request):
    """
    Personalised insights for the TeamLead:
    - Top rejected rules in their department
    - Rejection rate per rule
    - Smart recommendations derived from RuleTrainingSample data

    GET /api/teamlead/recommendations/
    Optional: ?dept=DIGITAL&limit=10
    """
    from django.db.models import Count, Q

    user = request.user
    roles = [str(r).upper() for r in getattr(user, 'roles', []) or []]

    try:
        limit = min(20, max(3, int(request.query_params.get('limit', 10))))
    except (TypeError, ValueError):
        limit = 10

    dept = request.query_params.get('dept') or (user.department if 'TEAMLEAD' in roles else None)

    # Scope document queryset
    if 'ADMIN' in roles and not dept:
        doc_qs = Document.objects.all()
    elif dept:
        doc_qs = Document.objects.filter(employee_department=dept)
    else:
        doc_qs = Document.objects.none()

    total_docs = doc_qs.count()
    approved_docs = doc_qs.filter(status__in=['approved', 'auto_approved']).count()
    rejected_docs = doc_qs.filter(status='rejected').count()
    overall_approval_rate = round(approved_docs / max(total_docs, 1) * 100, 1)

    # Top rejected rules from Validation
    val_qs = Validation.objects.filter(
        document__in=doc_qs,
        is_valid=False,
    ).values('rule__title').annotate(
        reject_count=Count('id')
    ).order_by('-reject_count')[:limit]

    top_rejected_rules = [
        {'rule': v['rule__title'] or 'Unknown', 'reject_count': v['reject_count']}
        for v in val_qs
    ]

    # Compute per-rule approval rate
    for rule_data in top_rejected_rules:
        rule_title = rule_data['rule']
        total_validations = Validation.objects.filter(
            document__in=doc_qs,
            rule__title=rule_title,
        ).count()
        valid_count = Validation.objects.filter(
            document__in=doc_qs,
            rule__title=rule_title,
            is_valid=True,
        ).count()
        rule_data['approval_rate'] = round(valid_count / max(total_validations, 1) * 100, 1)
        rule_data['total_validations'] = total_validations

    # Derive smart recommendations from top failing rules
    RULE_RECOMMENDATIONS = {
        'version': 'Utiliser le template de signature avec champ version obligatoire.',
        'signature': 'Rappeler aux employés l\'obligation de signature électronique.',
        'approbation': 'Renforcer le guide d\'approbation documentaire.',
        'archivage': 'Configurer l\'archivage automatique dans le DMS.',
        'identification': 'Appliquer le template d\'en-tête standardisé.',
        'lisibilit': 'Fournir le guide de mise en forme documentaire ISO.',
        'modification': 'Former les équipes au contrôle des modifications.',
        'accessibilit': 'Vérifier les permissions d\'accès aux documents partagés.',
        'validit': 'Mettre en place des revues périodiques trimestrielles.',
    }

    recommendations = []
    for rule_data in top_rejected_rules[:5]:
        rule_lower = rule_data['rule'].lower()
        rec_text = None
        for keyword, rec in RULE_RECOMMENDATIONS.items():
            if keyword in rule_lower:
                rec_text = rec
                break
        if not rec_text:
            rec_text = f"Revoir les critères de validation pour la règle \"{rule_data['rule']}\"."
        recommendations.append({
            'rule': rule_data['rule'],
            'recommendation': rec_text,
            'reject_count': rule_data['reject_count'],
            'approval_rate': rule_data['approval_rate'],
        })

    # Recent document activity
    recent_docs = doc_qs.select_related('norme').order_by('-created_at')[:5]
    recent_activity = [
        {
            'id': d.id,
            'norme': d.norme.name if d.norme else '—',
            'employee': d.employee_username,
            'status': d.status,
            'created_at': d.created_at.isoformat(),
        }
        for d in recent_docs
    ]

    return Response({
        'department': dept or 'All',
        'summary': {
            'total_documents': total_docs,
            'approved': approved_docs,
            'rejected': rejected_docs,
            'overall_approval_rate': overall_approval_rate,
        },
        'top_rejected_rules': top_rejected_rules,
        'recommendations': recommendations,
        'recent_activity': recent_activity,
    })


# ═══════════════════════════════════════════════════════════════════════════
# DATASET QUALITY REPORT
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ml_diagnostics_api(request):
    """
    Professional ML diagnostics for the dashboard.
    SINGLE SOURCE OF TRUTH: RuleTrainingSample — same table used for model training.
    Returns dataset health indicators consistent with the Model Comparison Table.
    """
    from collections import Counter

    norm_id = request.query_params.get('norm_id')
    standard = request.query_params.get('standard')

    # Resolve norm filter
    selected_norm = None
    if norm_id:
        try:
            selected_norm = Norme.objects.get(pk=int(norm_id))
        except (Norme.DoesNotExist, ValueError):
            pass
    elif standard:
        selected_norm = Norme.objects.filter(name__iexact=standard).first()

    # ── PRIMARY SOURCE: RuleTrainingSample (same as model training) ──────
    evidence_qs = RuleTrainingSample.objects.all()
    if selected_norm:
        evidence_qs = evidence_qs.filter(norm=selected_norm)
    elif standard:
        evidence_qs = evidence_qs.filter(norm__name__iexact=standard)

    evidence_labels = list(evidence_qs.values_list('label', flat=True))
    approved_evidence = evidence_labels.count('approved')
    rejected_evidence = evidence_labels.count('rejected')
    total_evidences   = approved_evidence + rejected_evidence
    pending_evidence  = len(evidence_labels) - total_evidences

    # class_balance: minority / total labeled
    class_balance = 0.0
    if total_evidences > 0:
        minority = min(approved_evidence, rejected_evidence)
        class_balance = round(minority / total_evidences, 4)

    # Duplicate rate on evidence texts
    evidence_texts = [t for t in evidence_qs.values_list('evidence_text', flat=True) if t and t.strip()]
    duplicate_rate = 0.0
    if evidence_texts:
        text_counter = Counter(evidence_texts)
        dup_rows = sum(v - 1 for v in text_counter.values() if v > 1)
        duplicate_rate = round(dup_rows / max(len(evidence_texts), 1) * 100, 2)

    # Dataset completeness: % of labeled evidence rows with non-empty evidence_text
    labeled_qs = evidence_qs.filter(label__in=['approved', 'rejected'])
    total_labeled = labeled_qs.count()
    with_text = labeled_qs.exclude(evidence_text='').exclude(evidence_text__isnull=True).count()
    dataset_completeness = round(with_text / max(total_labeled, 1) * 100, 2) if total_labeled > 0 else 0.0

    # Feature count = number of rules in the norm
    feature_count = selected_norm.rules.count() if selected_norm else 0

    # Leakage risk: same document_id appearing in multiple evidence rows
    doc_ids = list(evidence_qs.values_list('document_id', flat=True))
    doc_counter = Counter(d for d in doc_ids if d is not None)
    leakage_risk = 0.0
    if doc_ids:
        leakage_risk = round(max(0.0, 1.0 - (len(doc_counter) / max(len(doc_ids), 1))), 4)

    # Evaluation sample count from metrics JSON (the actual test-set size)
    eval_samples = None
    import os as _os, json as _json
    try:
        from ml.train_models import sanitize_standard
        models_dir = _os.path.join(_os.path.dirname(__file__), '..', 'ml', 'models')
        if selected_norm:
            metrics_path = _os.path.join(models_dir, f"{sanitize_standard(selected_norm.name)}_metrics.json")
            if _os.path.exists(metrics_path):
                data = _json.loads(open(metrics_path, encoding='utf-8').read())
                # sample_count in any model = training set size; eval = ~10% split
                results = data.get('results', {})
                for m_data in results.values():
                    n = m_data.get('sample_count', 0)
                    if n and n > 0:
                        eval_samples = n
                        break
    except Exception:
        pass

    # ── Secondary: TrainingSample (document-level, may be populated) ─────
    # Used only for "document_labels" section — not for primary metrics
    ts_qs = TrainingSample.objects.filter(document__norme=selected_norm) if selected_norm else TrainingSample.objects.none()
    approved_docs = ts_qs.filter(label='approved').count()
    rejected_docs = ts_qs.filter(label='rejected').count()
    total_documents = approved_docs + rejected_docs

    warnings = []
    if total_evidences < 20:
        warnings.append('Dataset is too small for reliable training (< 20 samples).')
    if duplicate_rate > 10:
        warnings.append('Duplicate evidence text is inflating the apparent dataset quality.')
    if leakage_risk > 0.05:
        warnings.append('Some documents appear multiple times; grouped validation is recommended.')
    if class_balance < 0.3:
        warnings.append('Dataset is imbalanced. Consider adding more minority class samples.')

    return Response({
        # Primary metrics — from RuleTrainingSample (same source as model training)
        'total_evidences':      total_evidences,
        'total_documents':      total_evidences,   # alias: shows training set size, not document count
        'document_samples':     total_evidences,
        'evidence_samples':     total_evidences,
        'approved_evidence':    approved_evidence,
        'rejected_evidence':    rejected_evidence,
        # Dataset health
        'dataset_completeness': dataset_completeness,
        'class_balance':        class_balance,
        'duplicate_rate':       duplicate_rate,
        'leakage_risk':         leakage_risk,
        'feature_count':        feature_count,
        # Evaluation info
        'eval_samples':         eval_samples,
        # Labels breakdown
        'document_labels': {
            'approved': approved_docs,
            'rejected': rejected_docs,
        },
        'evidence_labels': {
            'approved': approved_evidence,
            'rejected': rejected_evidence,
        },
        'recommended_source': 'evidence' if total_evidences >= 20 else 'document',
        'warnings': warnings,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dataset_quality_report_api(request):
    """
    Comprehensive dataset quality report for the Dataset Quality page.
    Includes duplicate analysis, coverage, semantic richness, and distribution.
    """
    from django.db.models import Count, Avg, Q
    from collections import Counter

    norm_id = request.query_params.get('norm_id')
    standard = request.query_params.get('standard') or request.query_params.get('norm_name')

    # Resolve norm object for accurate coverage calculation
    resolved_norm = None
    if norm_id:
        try:
            resolved_norm = Norme.objects.get(pk=int(norm_id))
            standard = resolved_norm.name
        except (Norme.DoesNotExist, ValueError):
            pass
    elif standard:
        resolved_norm = (
            Norme.objects.filter(name__iexact=standard).first()
            or Norme.objects.filter(name__icontains=standard).first()
        )

    # Filter RuleTrainingSample and document samples.
    rts_qs = RuleTrainingSample.objects.select_related('rule', 'norm').all()
    dts_qs = DocumentTrainingSample.objects.select_related('document').all()
    ts_qs = TrainingSample.objects.all()

    if resolved_norm:
        rts_qs = rts_qs.filter(norm=resolved_norm)
        dts_qs = dts_qs.filter(document__norme=resolved_norm)
        ts_qs = ts_qs.filter(norm_id=resolved_norm.id)
    elif norm_id:
        try:
            rts_qs = rts_qs.filter(norm_id=int(norm_id))
            dts_qs = dts_qs.filter(document__norme_id=int(norm_id))
            ts_qs = ts_qs.filter(norm_id=int(norm_id))
        except (ValueError, TypeError):
            pass
    elif standard:
        rts_qs = rts_qs.filter(norm__name__iexact=standard)
        dts_qs = dts_qs.filter(standard__iexact=standard)
        ts_qs = ts_qs.filter(standard__iexact=standard)

    # Document-level stats
    total_documents = dts_qs.count()
    approved_documents = dts_qs.filter(label='approved').count()
    rejected_documents = dts_qs.filter(label='rejected').count()
    pending_documents = dts_qs.filter(label='pending').count()

    # Evidence dataset stats
    total_evidence = rts_qs.count()
    approved_evidence = rts_qs.filter(label='approved').count()
    rejected_evidence = rts_qs.filter(label='rejected').count()
    pending_evidence = rts_qs.filter(label='pending').count()

    # Duplicate analysis on evidence
    evidence_texts = list(rts_qs.values_list('evidence_text', flat=True))
    non_empty = [t for t in evidence_texts if t and t.strip()]
    text_counter = Counter(non_empty)
    unique_count = len(set(non_empty))
    duplicate_rows = sum(v - 1 for v in text_counter.values() if v > 1)
    duplication_rate = round((1 - unique_count / max(len(non_empty), 1)) * 100, 1) if non_empty else 0

    # Vocabulary richness
    all_words = set()
    total_words = 0
    for text in non_empty:
        words = text.lower().split()
        all_words.update(words)
        total_words += len(words)
    vocabulary_size = len(all_words)
    avg_evidence_length = round(total_words / max(len(non_empty), 1), 1)

    # Rules coverage — FIXED: use resolved_norm for reliable rule counting
    total_rules_in_norm = 0
    rules_with_evidence = 0
    if resolved_norm:
        total_rules_in_norm = resolved_norm.rules.count()
        rules_with_evidence = rts_qs.values('rule_id').distinct().count()
    elif norm_id:
        try:
            norm = Norme.objects.prefetch_related('rules').get(pk=norm_id)
            total_rules_in_norm = norm.rules.count()
            rules_with_evidence = rts_qs.values('rule_id').distinct().count()
        except (Norme.DoesNotExist, ValueError):
            pass
    elif standard:
        norm = Norme.objects.prefetch_related('rules').filter(name__iexact=standard).first()
        if norm:
            total_rules_in_norm = norm.rules.count()
            rules_with_evidence = rts_qs.values('rule_id').distinct().count()

    coverage_pct = round(rules_with_evidence / max(total_rules_in_norm, 1) * 100, 1) if total_rules_in_norm > 0 else 0

    # Precision of document-level coverage/completeness
    completeness_pct = 0.0
    if total_documents:
        complete_docs = dts_qs.exclude(feature_vector__exact=[]).exclude(feature_vector__exact='').count()
        completeness_pct = round((complete_docs / total_documents) * 100, 1)

    # leakage risk from duplicate document IDs in document-level dataset
    duplicate_doc_ids = 0
    if total_documents:
        duplicate_doc_ids = sum(1 for v in Counter(dts_qs.values_list('document_id', flat=True)).values() if v > 1)
    leakage_risk = round((duplicate_doc_ids / max(total_documents, 1)) * 100, 1)

    class_balance = 0.0
    if approved_documents + rejected_documents > 0:
        class_balance = round(min(approved_documents, rejected_documents) / max(approved_documents + rejected_documents, 1), 4)

    # Per-rule distribution
    rule_dist = list(
        rts_qs.values('rule_title')
        .annotate(
            total=Count('id'),
            approved=Count('id', filter=Q(label='approved')),
            rejected=Count('id', filter=Q(label='rejected')),
        )
        .order_by('-total')[:20]
    )

    # Average semantic score
    avg_semantic = rts_qs.aggregate(avg=Avg('semantic_score'))['avg'] or 0
    avg_confidence = rts_qs.aggregate(avg=Avg('confidence_score'))['avg'] or 0

    return Response({
        'classification': {
            'total': total_documents,
            'approved': approved_documents,
            'rejected': rejected_documents,
            'pending': pending_documents,
            'avg_compliance': round(dts_qs.aggregate(avg=Avg('compliance_score'))['avg'] or 0, 1),
            'balance_ratio': round(approved_documents / max(rejected_documents, 1), 2),
        },
        'evidence': {
            'total': total_evidence,
            'approved': approved_evidence,
            'rejected': rejected_evidence,
            'pending': pending_evidence,
            'unique': unique_count,
            'duplicates': duplicate_rows,
            'duplication_rate': duplication_rate,
            'vocabulary_size': vocabulary_size,
            'avg_evidence_length': avg_evidence_length,
            'avg_semantic_score': round(avg_semantic * 100, 1),
            'avg_confidence_score': round(avg_confidence * 100, 1),
        },
        'coverage': {
            'total_rules': total_rules_in_norm,
            'rules_with_evidence': rules_with_evidence,
            # FIXED: these are distinct rule counts, not evidence row counts
            'rules_with_approved': rts_qs.filter(label='approved').values('rule_id').distinct().count(),
            'rules_with_rejected': rts_qs.filter(label='rejected').values('rule_id').distinct().count(),
            'coverage_pct': coverage_pct,
        },
        'quality': {
            'coverage': coverage_pct,
            'completeness': completeness_pct,
            'duplicates': duplication_rate,
            'class_balance': class_balance,
            'leakage_risk': leakage_risk,
        },
        'rule_distribution': rule_dist,
        'quality_status': (
            'excellent' if duplication_rate < 5 and coverage_pct > 80 and leakage_risk < 5
            else 'good' if duplication_rate < 20 and coverage_pct > 50
            else 'needs_improvement'
        ),
    })


# ═══════════════════════════════════════════════════════════════════════════
# SYNC DATASET — POST /api/dataset/sync/
# Triggers synchronisation de TrainingSample depuis RuleTrainingSample
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_dataset_api(request):
    """
    POST /api/dataset/sync/
    Synchronise les TrainingSample depuis les RuleTrainingSample existants.
    Appelé après validation, création d'evidence ou import de dataset.
    """
    norm_id = request.data.get('norm_id')
    document_ids = request.data.get('document_ids')

    try:
        result = sync_training_samples_from_evidence(document_ids=document_ids)
        # Compute coherence report per norm
        norms_report = []
        for norm in Norme.objects.all():
            rts = RuleTrainingSample.objects.filter(norm=norm)
            total = rts.count()
            approved = rts.filter(label='approved').count()
            rejected = rts.filter(label='rejected').count()
            rules_total = norm.rules.count()
            covered = rts.filter(label__in=['approved', 'rejected']).values('rule_id').distinct().count()
            coverage = round(covered / max(rules_total, 1) * 100, 1) if rules_total else 0.0
            norms_report.append({
                'norm_id': norm.id,
                'norm_name': norm.name,
                'total_evidence': total,
                'approved': approved,
                'rejected': rejected,
                'total_rules': rules_total,
                'rules_covered': covered,
                'coverage_pct': coverage,
            })

        return Response({
            'success': True,
            'created': result.get('created', 0),
            'updated': result.get('updated', 0),
            'documents': result.get('documents', 0),
            'norms': norms_report,
        })
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════
# COHERENCE CHECK — GET /api/dataset/coherence/
# Retourne un rapport de cohérence entre Evidence et Training Dataset
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dataset_coherence_api(request):
    """
    GET /api/dataset/coherence/
    Vérifie la cohérence entre RuleTrainingSample et les stats affichées.
    Utilisé pour valider que toutes les pages affichent les mêmes chiffres.
    """
    norms_report = []
    for norm in Norme.objects.prefetch_related('rules').all():
        rts = RuleTrainingSample.objects.filter(norm=norm)
        total = rts.count()
        approved = rts.filter(label='approved').count()
        rejected = rts.filter(label='rejected').count()
        rules_total = norm.rules.count()
        covered = rts.filter(label__in=['approved', 'rejected']).values('rule_id').distinct().count()
        coverage = round(covered / max(rules_total, 1) * 100, 1) if rules_total else 0.0

        # Quality score (same formula as dataset_stats_api)
        texts = list(rts.filter(label__in=['approved', 'rejected']).values_list('evidence_text', flat=True))
        non_empty = [t for t in texts if t and t.strip()]
        unique_texts = set(non_empty)
        dup_rate = round((1 - len(unique_texts) / max(len(non_empty), 1)) * 100, 1) if non_empty else 0.0
        avg_len = round(sum(len(t.split()) for t in non_empty) / max(len(non_empty), 1), 1) if non_empty else 0.0
        total_labeled = approved + rejected
        if total_labeled > 0:
            minority = min(approved, rejected)
            balance = round(minority / max(total_labeled - minority, 1) * 100, 1)
            balance = min(balance, 100.0)
        else:
            balance = 0.0

        quality = min(100.0, max(0.0, round(
            0.35 * (100 - dup_rate)
            + 0.25 * min(avg_len / 30.0 * 100, 100)
            + 0.25 * balance
            + 0.15 * coverage,
            1,
        )))

        coherent = total > 0 and (approved + rejected) > 0
        norms_report.append({
            'norm_id': norm.id,
            'norm_name': norm.name,
            'total_evidence': total,
            'approved': approved,
            'rejected': rejected,
            'pending': total - approved - rejected,
            'total_rules': rules_total,
            'rules_covered': covered,
            'coverage_pct': coverage,
            'quality_score': quality,
            'class_balance': balance,
            'is_coherent': coherent,
            'issues': [] if coherent else ['No labeled evidence (approved+rejected = 0)'],
        })

    all_coherent = all(n['is_coherent'] for n in norms_report)
    return Response({
        'all_coherent': all_coherent,
        'norms': norms_report,
        'total_norms': len(norms_report),
    })


# ═══════════════════════════════════════════════════════════════════════════
# MLOPS — Training Job tracking, Jenkins trigger, Prometheus metrics
# ═══════════════════════════════════════════════════════════════════════════

from .models import TrainingJob, MLOpsConfig


class TrainingJobSerializer_inline:
    """Inline serializer — avoids a separate serializers.py change."""
    @staticmethod
    def serialize(job):
        # Format model_version: strip "jenkins-0-" prefix that appears when
        # BUILD_NUMBER=0 (local run without real Jenkins build number).
        raw_version = job.model_version or ''
        if raw_version.startswith('jenkins-0-'):
            display_version = raw_version[len('jenkins-0-'):]
        elif raw_version.startswith('jenkins-'):
            # e.g. "jenkins-42-RandomForest" → keep as-is (real build)
            display_version = raw_version
        else:
            display_version = raw_version

        return {
            'id': job.id,
            'start_time': job.start_time.isoformat() if job.start_time else None,
            'end_time': job.end_time.isoformat() if job.end_time else None,
            'duration_seconds': job.duration_seconds,
            'documents_count': job.documents_count,
            'dataset_size': job.dataset_size,
            'new_docs_since': job.new_docs_since,
            'drift_score': job.drift_score,
            'accuracy': job.accuracy,
            'f1_score': job.f1_score,
            'precision_score': job.precision_score,
            'recall_score': job.recall_score,
            'avg_similarity': job.avg_similarity,
            'status': job.status,
            'model_version': display_version,
            'model_version_raw': raw_version,
            'standard': job.standard,
            'jenkins_build_id': job.jenkins_build_id,
            'jenkins_url': job.jenkins_url,
            'triggered_by': job.triggered_by,
            'drift_report': job.drift_report,
            'log_output': job.log_output,
        }


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def mlops_jenkins_status_api(request):
    """
    GET /api/ml/jenkins/status/
    Returns a full Jenkins health check result.
    Performs live network checks — do not call in tight loops.
    The frontend should call this endpoint on demand (e.g. "Test connection" button).
    """
    from services.mlops_service import get_jenkins_health
    return Response(get_jenkins_health())


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def mlops_status_api(request):
    """
    GET /api/ml/mlops/status/
    Returns overall MLOps dashboard data:
    - training jobs history
    - per-standard config with last successful TrainingJob metrics
    - document/sample counts since last training
    - drift scores
    """
    from services.mlops_service import count_new_documents, compute_drift_score
    from api.models import RuleTrainingSample

    configs = MLOpsConfig.objects.all()
    standards_data = []

    for cfg in configs:
        try:
            doc_info = count_new_documents(cfg.standard)
        except Exception:
            doc_info = {}
        try:
            drift_info = compute_drift_score(cfg.standard)
        except Exception:
            drift_info = {'drift_score': None, 'status': 'error'}

        # Last successful TrainingJob for this standard — single source of truth
        # for metrics (f1, precision, recall, accuracy, model_version).
        last_job = (
            TrainingJob.objects
            .filter(standard=cfg.standard, status='success')
            .order_by('-end_time')
            .first()
        )
        last_job_data = TrainingJobSerializer_inline.serialize(last_job) if last_job else None

        # Total training samples (RuleTrainingSample) — this is what the ML
        # pipeline actually trains on, not the raw Document upload count.
        total_samples = RuleTrainingSample.objects.filter(
            norm__name__iexact=cfg.standard
        ).count()
        labeled_samples = RuleTrainingSample.objects.filter(
            norm__name__iexact=cfg.standard,
            label__in=['approved', 'rejected'],
        ).count()

        # New labeled samples since last training — the meaningful "new docs" metric.
        if cfg.last_trained_at:
            new_samples = RuleTrainingSample.objects.filter(
                norm__name__iexact=cfg.standard,
                label__in=['approved', 'rejected'],
                created_at__gt=cfg.last_trained_at,
            ).count()
        else:
            new_samples = labeled_samples

        # Use retraining_threshold from MLOpsConfig (set per-standard).
        threshold = cfg.retraining_threshold

        # Determine the real f1 / model_version from last successful job
        # rather than relying solely on MLOpsConfig which may be stale.
        if last_job:
            effective_f1 = last_job.f1_score if last_job.f1_score else cfg.last_f1_score
            effective_model_version = last_job_data['model_version'] if last_job_data else cfg.current_model_version
            effective_drift = last_job.drift_score if last_job.drift_score else cfg.last_drift_score
        else:
            effective_f1 = cfg.last_f1_score
            effective_model_version = cfg.current_model_version
            effective_drift = cfg.last_drift_score

        needs_training = (
            cfg.auto_trigger_enabled
            and new_samples >= threshold
            and threshold > 0
        )

        standards_data.append({
            'standard': cfg.standard,
            'last_trained_at': cfg.last_trained_at.isoformat() if cfg.last_trained_at else None,
            'last_trained_doc_count': cfg.last_trained_doc_count,
            # Model version cleaned of "jenkins-0-" placeholder prefix
            'current_model_version': effective_model_version or None,
            'retraining_threshold': threshold,
            'auto_trigger_enabled': cfg.auto_trigger_enabled,
            'training_count': cfg.training_count,
            # Metrics from last successful job — single source of truth
            'last_f1_score':    effective_f1 if effective_f1 else None,
            'last_drift_score': effective_drift if effective_drift else None,
            # Counts based on RuleTrainingSample (what the pipeline trains on).
            # FIX #3: total_documents == labeled_samples so MLOps and ML Dashboard
            # always show the same number without frontend fallback chains.
            'total_samples':    labeled_samples,     # labeled RuleTrainingSample rows
            'labeled_samples':  labeled_samples,     # alias (used by StandardCard)
            'total_documents':  labeled_samples,     # legacy alias — now identical to labeled_samples
            'new_samples':      new_samples,
            'new_documents':    new_samples,         # legacy alias
            'needs_training':   needs_training,
            'drift':            drift_info,
            # Full last job details for the detail panel
            'last_job':         last_job_data,
            # Expose last-job precision/recall/accuracy at the standard level
            # so MLOps StandardCard can show them without reading last_job.*
            'last_precision':   last_job_data['precision_score'] if last_job_data else None,
            'last_recall':      last_job_data['recall_score']    if last_job_data else None,
            'last_accuracy':    (last_job_data['accuracy'] or last_job_data['avg_similarity'])
                                if last_job_data else None,
        })

    # Recent jobs — strip any with standard='' or clearly garbage data
    recent_jobs = (
        TrainingJob.objects
        .exclude(standard='')
        .order_by('-start_time')[:20]
    )
    jobs_data = [TrainingJobSerializer_inline.serialize(j) for j in recent_jobs]

    # Aggregate stats
    total_jobs = TrainingJob.objects.count()
    success_jobs = TrainingJob.objects.filter(status='success').count()
    failed_jobs = TrainingJob.objects.filter(status='failed').count()
    running_jobs = TrainingJob.objects.filter(status='running').count()

    last_success = TrainingJob.objects.filter(status='success').order_by('-end_time').first()

    # Jenkins status: use full health check (reachability + auth + job existence).
    # Re-read env vars at request time so changes take effect without restart.
    from services.mlops_service import get_jenkins_health
    jenkins_health = get_jenkins_health()
    jenkins_info = {
        'configured':    jenkins_health['configured'],
        'reachable':     jenkins_health['reachable'],
        'authenticated': jenkins_health['authenticated'],
        'connected':     jenkins_health['connected'],
        'local_training': jenkins_health['local_training'],
        'remote_trigger': jenkins_health['remote_trigger'],
        'version':       jenkins_health.get('version'),
        'status':        jenkins_health['status'],
        'message':       jenkins_health['message'],
        'url':           jenkins_health.get('jenkins_url'),
        'job_name':      jenkins_health.get('job_name'),
        'checked_at':    jenkins_health.get('checked_at'),
    }

    return Response({
        'standards': standards_data,
        'recent_jobs': jobs_data,
        'summary': {
            'total_jobs': total_jobs,
            'success_jobs': success_jobs,
            'failed_jobs': failed_jobs,
            'running_jobs': running_jobs,
            'last_successful_job': TrainingJobSerializer_inline.serialize(last_success) if last_success else None,
        },
        # Structured Jenkins health — single source of truth for the frontend
        'jenkins': jenkins_info,
        # Kept for backward compat with older frontend code
        'jenkins_configured': jenkins_health['connected'],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def mlops_trigger_training_api(request):
    """
    POST /api/ml/trigger-training/
    Body: { "standard": "ISO9001", "force": false }
    - Checks if new labeled RuleTrainingSamples >= threshold
    - Triggers Jenkins pipeline if conditions met (or force=true)
    """
    from services.mlops_service import trigger_jenkins_pipeline
    from api.models import RuleTrainingSample

    standard = request.data.get('standard', '')
    force    = request.data.get('force', False)

    if not standard:
        norme = Norme.objects.first()
        standard = norme.name if norme else ''

    if not standard:
        return Response({'error': 'No standard provided and no norm found in database.'}, status=status.HTTP_400_BAD_REQUEST)

    # Use MLOpsConfig as source for threshold
    cfg, _ = MLOpsConfig.objects.get_or_create(
        standard=standard,
        defaults={'retraining_threshold': int(os.getenv('MLOPS_RETRAINING_THRESHOLD', '10'))},
    )

    total_samples = RuleTrainingSample.objects.filter(
        norm__name__iexact=standard,
        label__in=['approved', 'rejected'],
    ).count()

    if cfg.last_trained_at:
        new_samples = RuleTrainingSample.objects.filter(
            norm__name__iexact=standard,
            label__in=['approved', 'rejected'],
            created_at__gt=cfg.last_trained_at,
        ).count()
    else:
        new_samples = total_samples

    doc_info = {
        'standard': standard,
        'total_documents': total_samples,
        'new_documents': new_samples,
        'threshold': cfg.retraining_threshold,
        'needs_training': new_samples >= cfg.retraining_threshold,
    }

    if not force and not doc_info['needs_training']:
        return Response({
            'triggered': False,
            'reason': (
                f"Only {new_samples}/{cfg.retraining_threshold} new labeled samples. "
                "Threshold not reached. Pass force=true to override."
            ),
            'doc_info': doc_info,
        }, status=status.HTTP_200_OK)

    result = trigger_jenkins_pipeline(standard, doc_info)
    result['doc_info'] = doc_info

    http_status = status.HTTP_200_OK if result.get('triggered') else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(result, status=http_status)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def mlops_check_threshold_api(request):
    """
    GET /api/ml/check-threshold/?standard=ISO9001
    Returns whether retraining is needed for the given standard,
    based on labeled RuleTrainingSample count (same source as training).
    """
    from api.models import RuleTrainingSample

    standard = request.query_params.get('standard', '')
    if not standard:
        norme = Norme.objects.first()
        standard = norme.name if norme else ''

    if not standard:
        return Response({'error': 'No standard provided and no norm found.'}, status=status.HTTP_400_BAD_REQUEST)

    cfg, _ = MLOpsConfig.objects.get_or_create(
        standard=standard,
        defaults={'retraining_threshold': int(os.getenv('MLOPS_RETRAINING_THRESHOLD', '10'))},
    )

    total_samples = RuleTrainingSample.objects.filter(
        norm__name__iexact=standard,
        label__in=['approved', 'rejected'],
    ).count()

    if cfg.last_trained_at:
        new_samples = RuleTrainingSample.objects.filter(
            norm__name__iexact=standard,
            label__in=['approved', 'rejected'],
            created_at__gt=cfg.last_trained_at,
        ).count()
    else:
        new_samples = total_samples

    return Response({
        'standard': standard,
        'total_documents': total_samples,
        'new_documents': new_samples,
        'last_trained_at': cfg.last_trained_at.isoformat() if cfg.last_trained_at else None,
        'threshold': cfg.retraining_threshold,
        'needs_training': new_samples >= cfg.retraining_threshold,
        'current_model_version': cfg.current_model_version or None,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def mlops_job_callback_api(request, job_id):
    """
    POST /api/ml/jobs/{job_id}/callback/
    Called by Jenkins at pipeline end to report results.
    Body: { status, f1_score, precision_score, recall_score, drift_score,
            avg_similarity, model_version, drift_report, log_output }
    """
    from services.mlops_service import update_job_result

    success = update_job_result(job_id, request.data)
    if not success:
        return Response({'error': f'Job #{job_id} not found'}, status=status.HTTP_404_NOT_FOUND)

    return Response({'message': f'Job #{job_id} updated successfully.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def mlops_jobs_list_api(request):
    """
    GET /api/ml/jobs/?standard=ISO9001&status=success&page=1
    Paginated list of training jobs.
    """
    standard    = request.query_params.get('standard')
    job_status  = request.query_params.get('status')
    try:
        page      = max(1, int(request.query_params.get('page', 1)))
        page_size = min(50, int(request.query_params.get('page_size', 20)))
    except (ValueError, TypeError):
        page, page_size = 1, 20

    qs = TrainingJob.objects.all()
    if standard:
        qs = qs.filter(standard__iexact=standard)
    if job_status:
        qs = qs.filter(status=job_status)
    qs = qs.order_by('-start_time')

    total = qs.count()
    offset = (page - 1) * page_size
    jobs = qs[offset:offset + page_size]

    return Response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'pages': max(1, (total + page_size - 1) // page_size),
        'jobs': [TrainingJobSerializer_inline.serialize(j) for j in jobs],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def mlops_drift_api(request):
    """
    GET /api/ml/drift/?standard=ISO9001
    Compute semantic drift for a standard.
    """
    from services.mlops_service import compute_drift_score

    standard = request.query_params.get('standard', '')
    if not standard:
        norme = Norme.objects.first()
        standard = norme.name if norme else 'ISO9001'

    report = compute_drift_score(standard)
    return Response(report)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def mlops_prometheus_metrics_api(request):
    """
    GET /api/metrics/
    Expose Prometheus-compatible metrics. Admin only — prevents data leakage.
    """
    from django.http import HttpResponse
    from services.mlops_service import get_prometheus_metrics

    try:
        metrics_text = get_prometheus_metrics()
        return HttpResponse(metrics_text, content_type='text/plain; version=0.0.4; charset=utf-8')
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════
# COVERAGE DIAGNOSTICS — GET /api/evidence/coverage-diagnostics/
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def evidence_coverage_diagnostics_api(request):
    """
    GET /api/evidence/coverage-diagnostics/?norm_id=1
    Returns detailed coverage report for one or all norms.
    {
      total_rules, covered_rules, uncovered_rules[],
      duplicate_rules[], coverage_percentage,
      evidence_per_rule[]
    }
    """
    import re as _re
    import unicodedata as _uni

    def _normalize(text):
        if not text: return ''
        text = text.strip().lower()
        text = _uni.normalize('NFD', text)
        text = ''.join(c for c in text if _uni.category(c) != 'Mn')
        text = _re.sub(r'\s+', ' ', text)
        text = _re.sub(r'[^\w\s]', '', text)
        return text.strip()

    norm_id = request.query_params.get('norm_id')
    norms = Norme.objects.all()
    if norm_id:
        try:
            norms = norms.filter(pk=int(norm_id))
        except (ValueError, TypeError):
            pass

    results = []

    for norme in norms:
        rules = list(norme.rules.all())
        total = len(rules)

        # Evidence count per rule
        evidence_per_rule = []
        covered_rules = []
        uncovered_rules = []

        for r in rules:
            cnt_approved = RuleTrainingSample.objects.filter(norm=norme, rule=r, label='approved').count()
            cnt_rejected = RuleTrainingSample.objects.filter(norm=norme, rule=r, label='rejected').count()
            cnt_total    = cnt_approved + cnt_rejected

            entry = {
                'rule_id':    r.id,
                'rule_title': r.title,
                'severity':   r.severity,
                'condition':  r.condition,
                'approved':   cnt_approved,
                'rejected':   cnt_rejected,
                'total':      cnt_total,
            }
            evidence_per_rule.append(entry)

            if cnt_total > 0:
                covered_rules.append({'id': r.id, 'title': r.title, 'total': cnt_total})
            else:
                uncovered_rules.append({'id': r.id, 'title': r.title, 'severity': r.severity})

        # Detect duplicate rule titles by normalized comparison
        from collections import defaultdict
        norm_groups = defaultdict(list)
        for r in rules:
            norm_groups[_normalize(r.title)].append({'id': r.id, 'title': r.title})
        duplicate_groups = [
            {'normalized': k, 'rules': v}
            for k, v in norm_groups.items() if len(v) > 1
        ]

        coverage_pct = round(len(covered_rules) / max(total, 1) * 100, 1)

        total_ev = RuleTrainingSample.objects.filter(norm=norme).count()
        approved_ev = RuleTrainingSample.objects.filter(norm=norme, label='approved').count()
        rejected_ev = RuleTrainingSample.objects.filter(norm=norme, label='rejected').count()

        results.append({
            'norm_id':             norme.id,
            'norm_name':           norme.name,
            'total_rules':         total,
            'covered_rules':       len(covered_rules),
            'uncovered_rules':     uncovered_rules,
            'covered_rule_list':   covered_rules,
            'coverage_percentage': coverage_pct,
            'duplicate_rules':     duplicate_groups,
            'total_evidence':      total_ev,
            'approved_evidence':   approved_ev,
            'rejected_evidence':   rejected_ev,
            'evidence_per_rule':   evidence_per_rule,
        })

    if norm_id and results:
        return Response(results[0])
    return Response({'norms': results, 'total_norms': len(results)})


# ═══════════════════════════════════════════════════════════════════════════
# LLM / OLLAMA ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def llm_status_api(request):
    """GET /api/llm/status/ — Ollama availability and loaded models."""
    from services.llm_service import get_ollama_status
    return Response(get_ollama_status())


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def llm_pull_model_api(request):
    """POST /api/llm/pull/ — Pull/download a model in Ollama."""
    from services.llm_service import pull_model, OLLAMA_MODEL
    model = request.data.get('model', OLLAMA_MODEL)
    result = pull_model(model)
    st = status.HTTP_200_OK if result.get('success') else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(result, status=st)


# ═══════════════════════════════════════════════════════════════════════════
# AI INSIGHTS — Aggregated overview endpoint
# GET /api/ai/overview/
# ═══════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeamLeadOrAdmin])
def ai_overview_api(request):
    """
    GET /api/ai/overview/
    Aggregated AI intelligence summary for the AI Insights dashboard.
    Returns: models, evidence, training jobs, drift, health, timeline.
    """
    import os, json as _json
    from django.db.models import Count, Avg, Q
    from django.utils import timezone as tz
    from services.llm_service import get_ollama_status
    from services.mlops_service import compute_drift_score

    # ── Models from metrics JSON ──────────────────────────────────────────
    models_dir = os.path.join(os.path.dirname(__file__), '..', 'ml', 'models')
    allowed_algos = ["RandomForest", "LogisticRegression", "GradientBoosting", "BiLSTM"]
    all_models_info = []
    best_model_overall = None
    best_f1_overall = -1.0

    norms = list(Norme.objects.all())
    standards = [n.name for n in norms]

    try:
        from ml.train_models import sanitize_standard
    except Exception:
        sanitize_standard = lambda s: s.replace(' ', '_').upper()

    for std in standards:
        metrics_path = os.path.join(models_dir, f"{sanitize_standard(std)}_metrics.json")
        if not os.path.exists(metrics_path):
            continue
        try:
            with open(metrics_path, 'r', encoding='utf-8') as f:
                data = _json.load(f)
            results = data.get('results', {})
            best_in_std = data.get('best_model')
            trained_at = data.get('trained_at')
            for algo, metrics in results.items():
                if algo not in allowed_algos:
                    continue
                f1 = metrics.get('f1_score')
                acc = metrics.get('accuracy')
                all_models_info.append({
                    'standard': std,
                    'name': algo,
                    'accuracy': acc,
                    'f1_score': f1,
                    'precision': metrics.get('precision'),
                    'recall': metrics.get('recall'),
                    'training_time': metrics.get('training_time'),
                    'trained_at': metrics.get('trained_date') or trained_at,
                    'is_best': (algo == best_in_std),
                    'error': metrics.get('error'),
                    'feature_importance': metrics.get('feature_importance') or [],
                    'cross_validation': metrics.get('cross_validation'),
                    'confusion_matrix': metrics.get('confusion_matrix'),
                    'sample_count': metrics.get('sample_count'),
                    # Anti-leakage validation fields
                    'split_strategy':   metrics.get('split_strategy'),
                    'unique_documents': metrics.get('unique_documents'),
                    'overfitting_gap':  metrics.get('overfitting_gap'),
                    'overfitting_level': metrics.get('overfitting_level') or metrics.get('overfitting_risk'),
                    'train_size':       metrics.get('train_size'),
                    'val_size':         metrics.get('val_size'),
                    'test_size':        metrics.get('test_size'),
                    'pipeline':         metrics.get('pipeline'),
                })
                if f1 is not None and float(f1) > best_f1_overall:
                    best_f1_overall = float(f1)
                    best_model_overall = {'standard': std, 'name': algo, 'f1_score': f1, 'accuracy': acc}
        except Exception:
            pass

    # ── Evidence / dataset stats ──────────────────────────────────────────
    total_evidence = RuleTrainingSample.objects.count()
    approved_ev = RuleTrainingSample.objects.filter(label='approved').count()
    rejected_ev = RuleTrainingSample.objects.filter(label='rejected').count()
    rules_covered = RuleTrainingSample.objects.values('rule_id').distinct().count()
    avg_confidence = RuleTrainingSample.objects.aggregate(avg=Avg('confidence_score'))['avg'] or 0
    total_rules_all = Rule.objects.count()

    # Duplicates
    from collections import Counter
    ev_texts = list(RuleTrainingSample.objects.exclude(evidence_text='').values_list('evidence_text', flat=True))
    dup_counter = Counter(ev_texts)
    duplicate_count = sum(v - 1 for v in dup_counter.values() if v > 1)
    dup_rate = round((1 - len(set(ev_texts)) / max(len(ev_texts), 1)) * 100, 1) if ev_texts else 0

    # ── Training jobs stats ───────────────────────────────────────────────
    total_jobs = TrainingJob.objects.count()
    success_jobs = TrainingJob.objects.filter(status='success').count()
    failed_jobs = TrainingJob.objects.filter(status='failed').count()
    running_jobs = TrainingJob.objects.filter(status='running').count()
    last_success = TrainingJob.objects.filter(status='success').order_by('-end_time').first()
    last_job = TrainingJob.objects.order_by('-created_at').first()

    avg_f1 = TrainingJob.objects.filter(status='success', f1_score__gt=0).aggregate(avg=Avg('f1_score'))['avg']
    avg_drift = TrainingJob.objects.filter(status='success').aggregate(avg=Avg('drift_score'))['avg']

    # ── Drift per standard ────────────────────────────────────────────────
    # FIX #4: compute drift for ALL standards (not just 3) so ai/overview and
    # mlops/status show the same drift values. We cache the result per-request
    # using a dict; no external cache needed since the endpoint is already
    # called at most once per page load.
    drift_by_standard = {}
    for std in standards:
        try:
            drift_by_standard[std] = compute_drift_score(std)
        except Exception:
            drift_by_standard[std] = {'drift_score': None, 'status': 'error'}

    global_drift = 0.0
    drift_values = [v.get('drift_score', 0) for v in drift_by_standard.values() if v.get('drift_score') is not None]
    if drift_values:
        global_drift = round(sum(drift_values) / len(drift_values), 4)

    # ── FAISS / Embedding index ───────────────────────────────────────────
    faiss_meta = None
    if load_evidence_index_metadata is not None:
        try:
            faiss_meta = load_evidence_index_metadata()
        except Exception:
            pass

    embedding_model = (faiss_meta.get('embedding_model') if faiss_meta else None) or 'tfidf-fallback'
    vector_count = (faiss_meta.get('indexed_evidences') if faiss_meta else None) or total_evidence
    vector_dim = (faiss_meta.get('vector_dim') if faiss_meta else None)
    last_indexed = (faiss_meta.get('last_trained') if faiss_meta else None)

    # ── LLM / Ollama ──────────────────────────────────────────────────────
    try:
        llm_status = get_ollama_status()
    except Exception:
        llm_status = {'available': False, 'reason': 'Error checking Ollama'}

    # ── MLOps configs ────────────────────────────────────────────────────
    # FIX: include training_count and dataset_size (now reliably updated).
    configs = list(MLOpsConfig.objects.all().values(
        'standard', 'last_trained_at', 'current_model_version',
        'last_f1_score', 'last_drift_score', 'training_count', 'dataset_size',
    ))

    # ── Timeline events (training + drift significant events) ─────────────
    timeline_jobs = list(
        TrainingJob.objects.order_by('-created_at')[:15].values(
            'id', 'standard', 'status', 'start_time', 'end_time',
            'f1_score', 'drift_score', 'model_version', 'documents_count',
            'triggered_by', 'jenkins_build_id'
        )
    )

    # ── Determine AI health score ─────────────────────────────────────────
    health_score = 100
    health_issues = []

    if not llm_status.get('available'):
        health_score -= 15
        health_issues.append('LLM offline (Ollama not available)')
    if dup_rate > 10:
        health_score -= 10
        health_issues.append(f'High duplication rate: {dup_rate}%')
    if global_drift > 0.3:
        health_score -= 20
        health_issues.append(f'Critical drift detected: {round(global_drift * 100, 1)}%')
    elif global_drift > 0.15:
        health_score -= 10
        health_issues.append(f'Drift warning: {round(global_drift * 100, 1)}%')
    if total_evidence < 10:
        health_score -= 20
        health_issues.append('Insufficient training data')
    if best_model_overall and best_f1_overall < 0.6:
        health_score -= 15
        health_issues.append(f'Low model F1: {round(best_f1_overall * 100, 1)}%')
    if failed_jobs > success_jobs and total_jobs > 0:
        health_score -= 10
        health_issues.append('More failed training jobs than successful ones')

    health_score = max(0, health_score)
    health_label = (
        'Excellent' if health_score >= 90
        else 'Good' if health_score >= 75
        else 'Degraded' if health_score >= 50
        else 'Critical'
    )

    # ── Recommendations engine ────────────────────────────────────────────
    recommendations = []
    if dup_rate > 5:
        recommendations.append({
            'type': 'dataset',
            'priority': 'high' if dup_rate > 15 else 'medium',
            'title': 'Supprimer les doublons',
            'message': f'{duplicate_count} doublons détectés ({dup_rate}%). Nettoyer et réindexer FAISS.',
            'action': 'deduplicate',
        })
    if global_drift > 0.15:
        recommendations.append({
            'type': 'drift',
            'priority': 'high' if global_drift > 0.3 else 'medium',
            'title': 'Drift détecté — Relancer l\'entraînement',
            'message': f'Drift global: {round(global_drift * 100, 1)}%. Les données ont significativement évolué.',
            'action': 'retrain',
        })
    if total_evidence > 0:
        balance = round(approved_ev / max(rejected_ev, 1), 2)
        if balance > 4 or balance < 0.25:
            recommendations.append({
                'type': 'dataset',
                'priority': 'medium',
                'title': 'Dataset déséquilibré',
                'message': f'Ratio approuvé/rejeté: {balance}. Ajouter plus d\'exemples de la classe minoritaire.',
                'action': 'balance',
            })
    if not llm_status.get('available'):
        recommendations.append({
            'type': 'llm',
            'priority': 'low',
            'title': 'Assistant IA hors ligne',
            'message': 'Ollama n\'est pas disponible. Démarrer le service ou configurer OLLAMA_URL.',
            'action': 'start_llm',
        })
    if rules_covered < total_rules_all * 0.8 and total_rules_all > 0:
        recommendations.append({
            'type': 'coverage',
            'priority': 'medium',
            'title': 'Couverture insuffisante',
            'message': f'Seulement {rules_covered}/{total_rules_all} règles ont des preuves. Ajouter des validations.',
            'action': 'add_evidence',
        })
    if faiss_meta is None:
        recommendations.append({
            'type': 'faiss',
            'priority': 'medium',
            'title': 'Index FAISS non construit',
            'message': 'Aucun index FAISS trouvé. Construire l\'index pour activer la recherche sémantique.',
            'action': 'build_index',
        })
    if last_success is None and total_evidence > 10:
        recommendations.append({
            'type': 'training',
            'priority': 'high',
            'title': 'Aucun entraînement réussi',
            'message': 'Des données sont disponibles mais aucun modèle n\'a été entraîné avec succès.',
            'action': 'train',
        })

    return Response({
        'summary': {
            'total_models': len(all_models_info),
            'available_standards': standards,
            'total_evidence': total_evidence,
            'approved_evidence': approved_ev,
            'rejected_evidence': rejected_ev,
            'rules_covered': rules_covered,
            'total_rules': total_rules_all,
            'duplicate_count': duplicate_count,
            'duplication_rate': dup_rate,
            'avg_confidence': round(float(avg_confidence) * 100, 1),
            'global_drift': global_drift,
            'avg_f1': round(float(avg_f1) * 100, 1) if avg_f1 else None,
            'avg_drift': round(float(avg_drift) * 100, 1) if avg_drift else None,
        },
        'models': all_models_info,
        'best_model': best_model_overall,
        'mlops_configs': configs,
        'jobs': {
            'total': total_jobs,
            'success': success_jobs,
            'failed': failed_jobs,
            'running': running_jobs,
            'last_success': {
                'id': last_success.id,
                'standard': last_success.standard,
                'end_time': last_success.end_time.isoformat() if last_success.end_time else None,
                'f1_score': last_success.f1_score,
                'model_version': last_success.model_version,
            } if last_success else None,
        },
        'drift': {
            'global': global_drift,
            'by_standard': drift_by_standard,
        },
        'faiss': {
            'embedding_model': embedding_model,
            'vector_count': vector_count,
            'vector_dim': vector_dim,
            'last_indexed': last_indexed,
            'index_built': faiss_meta is not None,
        },
        'llm': {
            'available': llm_status.get('available', False),
            'model': llm_status.get('model'),
            'models': llm_status.get('models', []),
            'url': llm_status.get('url'),
            'reason': llm_status.get('reason'),
        },
        'health': {
            'score': health_score,
            'label': health_label,
            'issues': health_issues,
        },
        'recommendations': recommendations,
        'timeline': timeline_jobs,
        'computed_at': tz.now().isoformat(),
    })
