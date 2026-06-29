"""security/urls.py — URL routing for the Document Security Analysis app."""
from django.urls import path

from .views import (
    document_security_analysis,
    reanalyze_document_security,
    security_dashboard,
    security_dashboard_statistics,
    security_dashboard_high_risk,
)

urlpatterns = [
    path('documents/<int:document_id>/analysis/',  document_security_analysis,       name='doc-security-analysis'),
    path('documents/<int:document_id>/reanalyze/', reanalyze_document_security,      name='doc-security-reanalyze'),
    path('dashboard/',                             security_dashboard,               name='security-dashboard'),
    path('dashboard/statistics/',                  security_dashboard_statistics,    name='security-dashboard-statistics'),
    path('dashboard/high-risk/',                   security_dashboard_high_risk,     name='security-dashboard-high-risk'),
]
