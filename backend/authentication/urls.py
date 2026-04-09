from django.urls import path
from .views import LoginView, GetUserProfileView
from .admin_views import CreateTestUserView
from .setup_views import InitializeAdminView, GetAdminStatusView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('me/', GetUserProfileView.as_view(), name='user-profile'),
    path('admin/test-users/', CreateTestUserView.as_view(), name='create-test-user'),
    path('setup-admin/', InitializeAdminView.as_view(), name='setup-admin'),
    path('admin-status/', GetAdminStatusView.as_view(), name='admin-status'),
]