from django.urls import path
from .views import ProtectedView, AdminView, TeamLeadView, EmployeeView

urlpatterns = [
    path('protected/', ProtectedView.as_view(), name='protected'),
    path('admin/', AdminView.as_view(), name='admin'),
    path('teamlead/', TeamLeadView.as_view(), name='teamlead'),
    path('employee/', EmployeeView.as_view(), name='employee'),
]