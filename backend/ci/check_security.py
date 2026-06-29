# ci/check_security.py — Stage 4.5: validate security app imports and model
import os
import sys

_HERE    = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

errors = []

# ── 1. Model import ───────────────────────────────────────────────────────────
try:
    from security.models import DocumentSecurityAnalysis
    print('[OK] security.models.DocumentSecurityAnalysis imported')
except ImportError as exc:
    errors.append(f'[FAIL] Cannot import DocumentSecurityAnalysis: {exc}')

# ── 2. Model fields ───────────────────────────────────────────────────────────
try:
    fields = {f.name for f in DocumentSecurityAnalysis._meta.get_fields()}
    required = {
        'document', 'pii_count', 'pii_types', 'secret_count', 'secret_types',
        'confidentiality_level', 'confidentiality_score', 'risk_score', 'risk_level',
        'gdpr_status', 'recommendations', 'analysis_date', 'analysis_version',
    }
    missing = required - fields
    if missing:
        errors.append(f'[FAIL] Missing model fields: {missing}')
    else:
        print('[OK] All required model fields present')
except Exception as exc:
    errors.append(f'[FAIL] Field check error: {exc}')

# ── 3. Table exists in DB ─────────────────────────────────────────────────────
try:
    count = DocumentSecurityAnalysis.objects.count()
    print(f'[OK] DocumentSecurityAnalysis table accessible — {count} records')
except Exception as exc:
    errors.append(f'[FAIL] DB table not accessible: {exc}. Run: manage.py migrate')

# ── 4. Serializer import ──────────────────────────────────────────────────────
try:
    from security.serializers import DocumentSecurityAnalysisSerializer
    print('[OK] security.serializers imported')
except ImportError as exc:
    errors.append(f'[FAIL] Cannot import serializers: {exc}')

# ── 5. Orchestrator service import ────────────────────────────────────────────
try:
    from services.security_analysis import run_security_analysis, ANALYSIS_VERSION
    print(f'[OK] security_analysis orchestrator imported — version {ANALYSIS_VERSION}')
except ImportError as exc:
    errors.append(f'[FAIL] Cannot import security_analysis service: {exc}')

# ── 6. Sub-detectors import ───────────────────────────────────────────────────
detectors = [
    ('services.security.pii_detector',          'detect_pii'),
    ('services.security.secret_detector',       'detect_secrets'),
    ('services.security.metadata_analyzer',     'analyze_metadata'),
    ('services.security.risk_scoring',          'compute_scores'),
    ('services.security.gdpr_checker',          'check_gdpr'),
    ('services.security.recommendation_engine', 'generate_recommendations'),
]
for module_path, fn_name in detectors:
    try:
        module = __import__(module_path, fromlist=[fn_name])
        getattr(module, fn_name)
        print(f'[OK] {module_path}.{fn_name}')
    except (ImportError, AttributeError) as exc:
        errors.append(f'[FAIL] {module_path}.{fn_name}: {exc}')

# ── 7. URL routing ────────────────────────────────────────────────────────────
try:
    from django.urls import reverse
    # Test one named URL to confirm routing is wired
    reverse('doc-security-analysis', kwargs={'document_id': 1})
    print('[OK] security URL routing operational')
except Exception as exc:
    errors.append(f'[FAIL] URL routing error: {exc}')

# ── Result ────────────────────────────────────────────────────────────────────
if errors:
    print('\n[SECURITY CHECK FAILED]')
    for e in errors:
        print(e)
    sys.exit(1)

print('\n[OK] Security Analysis module fully operational — no regressions detected.')
