from django.urls import path
from .views import (
    UserListCreateView,
    UserDetailView,
    DepartmentListView,
    DepartmentDetailView,
    RoleListView,
    AuditLogListView,
)

app_name = 'rbac'

urlpatterns = [
    # User management
    path('users/', UserListCreateView.as_view(), name='user-list-create'),
    path('users/<int:user_id>/', UserDetailView.as_view(), name='user-detail'),
    
    # Departments
    path('departments/', DepartmentListView.as_view(), name='department-list'),
    path('departments/<str:department_code>/', DepartmentDetailView.as_view(), name='department-detail'),
    
    # Roles
    path('roles/', RoleListView.as_view(), name='role-list'),
    
    # Audit logs
    path('audit-logs/', AuditLogListView.as_view(), name='audit-log-list'),
]
