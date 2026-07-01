"""security/urls.py — URL routing for the Document Security Analysis app."""
from django.urls import path

from .views import (
    document_security_analysis,
    document_integrity_check,
    document_secure_view,
    document_secure_download,
    document_audit_history,
    reanalyze_document_security,
    security_dashboard,
    security_dashboard_statistics,
    security_dashboard_high_risk,
    security_dashboard_admin,
    documents_list_for_security,
    scan_uploaded_file,
)

urlpatterns = [
    path('documents/list/',                          documents_list_for_security,   name='security-documents-list'),
    path('documents/<int:document_id>/analysis/',    document_security_analysis,    name='doc-security-analysis'),
    path('documents/<int:document_id>/integrity/',   document_integrity_check,      name='doc-integrity-check'),
    path('documents/<int:document_id>/view/',        document_secure_view,          name='doc-secure-view'),
    path('documents/<int:document_id>/download/',    document_secure_download,      name='doc-secure-download'),
    path('documents/<int:document_id>/audit/',       document_audit_history,        name='doc-audit-history'),
    path('documents/<int:document_id>/reanalyze/',   reanalyze_document_security,   name='doc-security-reanalyze'),
    path('scan/',                                    scan_uploaded_file,            name='security-scan-file'),
    path('dashboard/',                               security_dashboard,            name='security-dashboard'),
    path('dashboard/statistics/',                    security_dashboard_statistics, name='security-dashboard-statistics'),
    path('dashboard/high-risk/',                     security_dashboard_high_risk,  name='security-dashboard-high-risk'),
    path('dashboard/admin/',                         security_dashboard_admin,      name='security-dashboard-admin'),
]
