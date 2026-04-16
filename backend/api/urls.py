from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NormeViewSet, DocumentViewSet, ValidationViewSet

router = DefaultRouter()
router.register(r'normes', NormeViewSet, basename='norme')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'validations', ValidationViewSet, basename='validation')

urlpatterns = [
    path('', include(router.urls)),
]