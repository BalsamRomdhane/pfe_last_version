from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExtractFeaturesView, NormeViewSet, DocumentViewSet, ValidationViewSet,
    TrainingSampleViewSet, RuleTrainingSampleViewSet, train_model_api, train_models_api, semantic_search_api,
    norms_list_api, dataset_stats_api, ml_train_api, ml_models_api, ml_test_document_api,
    ml_train_evidence_api,
    analyze_document_compliance_api, get_supported_standards_api, get_standard_rules_api,
    retrain_compliance_models_api, update_similarity_threshold_api, get_compliance_service_status_api
)
from .views import evidence_index_api, evidence_status_api, rule_memory_api, search_evidence_api

router = DefaultRouter()
router.register(r'normes', NormeViewSet, basename='norme')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'validations', ValidationViewSet, basename='validation')
router.register(r'training-dataset', TrainingSampleViewSet, basename='training-dataset')
router.register(r'training-samples', TrainingSampleViewSet, basename='training-samples')
router.register(r'rule-training-samples', RuleTrainingSampleViewSet, basename='rule-training-sample')

urlpatterns = [
    path('extract-features/', ExtractFeaturesView.as_view(), name='extract-features'),
    path('semantic-search/', semantic_search_api, name='semantic-search'),
    path('train-model/', train_model_api, name='train-model'),
    path('train-models/', train_models_api, name='train-models'),
    
    # ML Dashboard endpoints
    path('norms/', norms_list_api, name='norms-list'),
    path('dataset-stats/', dataset_stats_api, name='dataset-stats'),
    path('ml/train/', ml_train_api, name='ml-train'),
    path('ml/train-evidence/', ml_train_evidence_api, name='ml-train-evidence'),
    path('ml/models/', ml_models_api, name='ml-models'),
    path('ml/test-document/', ml_test_document_api, name='ml-test-document'),
    path('evidence/index/', evidence_index_api, name='evidence-index'),
    path('evidence/status/', evidence_status_api, name='evidence-status'),

    # Compliance Analysis endpoints
    path('compliance/analyze/', analyze_document_compliance_api, name='analyze-compliance'),
    path('compliance/standards/', get_supported_standards_api, name='supported-standards'),
    path('compliance/rules/<str:standard>/', get_standard_rules_api, name='standard-rules'),
    path('compliance/retrain/', retrain_compliance_models_api, name='retrain-models'),
    path('compliance/threshold/', update_similarity_threshold_api, name='update-threshold'),
    path('compliance/status/', get_compliance_service_status_api, name='service-status'),
    path('rule-memory/', rule_memory_api, name='rule-memory'),
    path('search-evidence/', search_evidence_api, name='search-evidence'),

    path('', include(router.urls)),
]