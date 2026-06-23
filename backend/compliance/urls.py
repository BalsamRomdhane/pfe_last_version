from django.urls import path
from .views import (
    compliance_audit_log_api, compliance_coverage_api, compliance_coverage_standard_api,
    compliance_readiness_api, compliance_readiness_standard_api, compliance_maturity_api,
    compliance_quality_api, compliance_risks_api, compliance_risk_update_api,
    compliance_reviews_api, compliance_critical_controls_api,
    compliance_executive_dashboard_api, compliance_refresh_all_api,
)

urlpatterns = [
    path('audit-log/',                   compliance_audit_log_api,              name='compliance-audit-log'),
    path('coverage/',                    compliance_coverage_api,               name='compliance-coverage-all'),
    path('coverage/<str:standard>/',     compliance_coverage_standard_api,      name='compliance-coverage-standard'),
    path('readiness/',                   compliance_readiness_api,              name='compliance-readiness-all'),
    path('readiness/<str:standard>/',    compliance_readiness_standard_api,     name='compliance-readiness-standard'),
    path('maturity/',                    compliance_maturity_api,               name='compliance-maturity'),
    path('quality/',                     compliance_quality_api,                name='compliance-quality'),
    path('risks/',                       compliance_risks_api,                  name='compliance-risks'),
    path('risks/<int:risk_id>/',         compliance_risk_update_api,            name='compliance-risk-update'),
    path('reviews/',                     compliance_reviews_api,                name='compliance-reviews'),
    path('critical-controls/',           compliance_critical_controls_api,      name='compliance-critical-controls'),
    path('executive-dashboard/',         compliance_executive_dashboard_api,    name='compliance-executive-dashboard'),
    path('refresh/',                     compliance_refresh_all_api,            name='compliance-refresh'),
]
