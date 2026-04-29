from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExtractFeaturesView, NormeViewSet, DocumentViewSet, ValidationViewSet, TrainingSampleViewSet

router = DefaultRouter()
router.register(r'normes', NormeViewSet, basename='norme')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'validations', ValidationViewSet, basename='validation')
router.register(r'training-dataset', TrainingSampleViewSet, basename='training-dataset')

urlpatterns = [
    path('extract-features/', ExtractFeaturesView.as_view(), name='extract-features'),
    path('', include(router.urls)),
]