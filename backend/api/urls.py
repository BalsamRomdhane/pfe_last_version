from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from rest_framework.routers import DefaultRouter
from .views import (
    ExtractFeaturesView, NormeViewSet, DocumentViewSet, ValidationViewSet,
    TrainingSampleViewSet, RuleTrainingSampleViewSet, train_model_api, train_models_api, semantic_search_api,
    norms_list_api, dataset_stats_api, ml_train_api, ml_models_api, ml_test_document_api, ml_test_evidence_api,
    ml_train_evidence_api,
    ml_diagnostics_api,
    analyze_document_compliance_api, get_supported_standards_api, get_standard_rules_api,
    retrain_compliance_models_api, update_similarity_threshold_api, get_compliance_service_status_api,
    dashboard_stats_api, document_stats_api, dataset_quality_report_api,
    # Innovation endpoints
    compliance_drift_api,
    document_pdf_report_api,
    compliance_chat_api,
    compliance_chat_stream_api,
    teamlead_recommendations_api,
    # MLOps endpoints
    mlops_status_api,
    mlops_trigger_training_api,
    mlops_check_threshold_api,
    mlops_job_callback_api,
    mlops_jobs_list_api,
    mlops_drift_api,
    mlops_prometheus_metrics_api,
    mlops_jenkins_status_api,
    # LLM endpoints
    llm_status_api,
    llm_pull_model_api,
    # AI Insights
    ai_overview_api,
)
from .views import evidence_index_api, evidence_status_api, evidence_duplicates_api, evidence_deduplicate_api, rule_memory_api, add_evidence_api, search_evidence_api, evidence_coverage_diagnostics_api
from .views import sync_dataset_api, dataset_coherence_api

router = DefaultRouter()
router.register(r'normes', NormeViewSet, basename='norme')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'validations', ValidationViewSet, basename='validation')
router.register(r'training-dataset', TrainingSampleViewSet, basename='training-dataset')
# NOTE: 'training-samples' was a duplicate registration removed to avoid URL conflicts.
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
    path('ml/diagnostics/', ml_diagnostics_api, name='ml-diagnostics'),
    path('ml/test-document/', ml_test_document_api, name='ml-test-document'),
    path('ml/test-evidence/', ml_test_evidence_api, name='ml-test-evidence'),
    path('evidence/index/', evidence_index_api, name='evidence-index'),
    path('evidence/status/', evidence_status_api, name='evidence-status'),
    path('evidence/duplicates/', evidence_duplicates_api, name='evidence-duplicates'),
    path('evidence/deduplicate/', evidence_deduplicate_api, name='evidence-deduplicate'),
    path('evidence/coverage-diagnostics/', evidence_coverage_diagnostics_api, name='evidence-coverage-diagnostics'),

    # Compliance Analysis endpoints
    path('compliance/analyze/', analyze_document_compliance_api, name='analyze-compliance'),
    path('compliance/standards/', get_supported_standards_api, name='supported-standards'),
    path('compliance/rules/<str:standard>/', get_standard_rules_api, name='standard-rules'),
    path('compliance/retrain/', retrain_compliance_models_api, name='retrain-models'),
    path('compliance/threshold/', update_similarity_threshold_api, name='update-threshold'),
    path('compliance/status/', get_compliance_service_status_api, name='service-status'),
    path('rule-memory/', rule_memory_api, name='rule-memory'),
    path('rule-memory/add/', add_evidence_api, name='add-evidence'),
    path('search-evidence/', search_evidence_api, name='search-evidence'),

    # Dashboard & Stats endpoints
    path('dashboard/stats/', dashboard_stats_api, name='dashboard-stats'),
    path('documents/stats/', document_stats_api, name='document-stats'),
    path('dataset/quality-report/', dataset_quality_report_api, name='dataset-quality-report'),
    path('dataset/sync/', sync_dataset_api, name='dataset-sync'),
    path('dataset/coherence/', dataset_coherence_api, name='dataset-coherence'),

    # ── Innovation endpoints ──────────────────────────────────────────────
    # Innovation 3 — Compliance Drift Detection
    path('compliance/drift/', compliance_drift_api, name='compliance-drift'),
    # Innovation 4 — PDF Report
    path('documents/<int:pk>/report/', document_pdf_report_api, name='document-pdf-report'),
    # Innovation 5 — Local Compliance Assistant
    path('compliance/chat/', compliance_chat_api, name='compliance-chat'),
    path('compliance/chat/stream/', csrf_exempt(compliance_chat_stream_api), name='compliance-chat-stream'),
    # Innovation 7 — TeamLead Recommendations
    path('teamlead/recommendations/', teamlead_recommendations_api, name='teamlead-recommendations'),

    # ── MLOps endpoints ───────────────────────────────────────────────────
    path('ml/mlops/status/',                  mlops_status_api,           name='mlops-status'),
    path('ml/jenkins/status/',                mlops_jenkins_status_api,   name='mlops-jenkins-status'),
    path('ml/trigger-training/',              mlops_trigger_training_api, name='mlops-trigger'),
    path('ml/check-threshold/',               mlops_check_threshold_api,  name='mlops-threshold'),
    path('ml/drift/',                         mlops_drift_api,            name='mlops-drift'),
    path('ml/jobs/',                          mlops_jobs_list_api,        name='mlops-jobs'),
    path('ml/jobs/<int:job_id>/callback/',    mlops_job_callback_api,     name='mlops-job-callback'),
    path('metrics/',                          mlops_prometheus_metrics_api, name='prometheus-metrics'),

    # ── LLM / Ollama endpoints ─────────────────────────────────────────────
    path('llm/status/',                       llm_status_api,             name='llm-status'),
    path('llm/pull/',                         llm_pull_model_api,         name='llm-pull'),

    # ── AI Insights aggregated overview ───────────────────────────────────
    path('ai/overview/',                      ai_overview_api,            name='ai-overview'),

    path('', include(router.urls)),
]