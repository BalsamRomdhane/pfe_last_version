from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExtractFeaturesView, NormeViewSet, DocumentViewSet, ValidationViewSet, 
    TrainingSampleViewSet, train_model_api, train_models_api, semantic_search_api,
    norms_list_api, dataset_stats_api, ml_train_api, ml_models_api, ml_test_document_api
)

router = DefaultRouter()
router.register(r'normes', NormeViewSet, basename='norme')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'validations', ValidationViewSet, basename='validation')
router.register(r'training-dataset', TrainingSampleViewSet, basename='training-dataset')

urlpatterns = [
    path('extract-features/', ExtractFeaturesView.as_view(), name='extract-features'),
    path('semantic-search/', semantic_search_api, name='semantic-search'),
    path('train-model/', train_model_api, name='train-model'),
    path('train-models/', train_models_api, name='train-models'),
    
    # ML Dashboard endpoints
    path('norms/', norms_list_api, name='norms-list'),
    path('dataset-stats/', dataset_stats_api, name='dataset-stats'),
    path('ml/train/', ml_train_api, name='ml-train'),
    path('ml/models/', ml_models_api, name='ml-models'),
    path('ml/test-document/', ml_test_document_api, name='ml-test-document'),
    
    path('', include(router.urls)),
]