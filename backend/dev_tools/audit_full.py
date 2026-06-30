import os, sys, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'enterprise_platform.settings'
sys.stdout.reconfigure(encoding='utf-8')
django.setup()

from django.conf import settings
from django.db import connection

print("=" * 60)
print("SECTION 1 — SECRETS EXPOSES")
print("=" * 60)
print("DJANGO_SECRET_KEY starts with 'insecure':", settings.SECRET_KEY.startswith('django-insecure'))
print("DEBUG:", settings.DEBUG)
print("ALLOWED_HOSTS:", settings.ALLOWED_HOSTS)
kc_secret = os.environ.get('KEYCLOAK_CLIENT_SECRET', getattr(settings, 'KEYCLOAK_CLIENT_SECRET', ''))
print("KEYCLOAK_CLIENT_SECRET is default:", kc_secret == 'd3XqSEHRtQHKXIEHC0GztCzgXojUOF9O')
kc_admin_pw = os.environ.get('KEYCLOAK_ADMIN_PASSWORD', getattr(settings, 'KEYCLOAK_ADMIN_PASSWORD', ''))
print("KEYCLOAK_ADMIN_PASSWORD is 'admin':", kc_admin_pw == 'admin')
print("CORS_ALLOW_CREDENTIALS:", settings.CORS_ALLOW_CREDENTIALS)
print("CSRF_COOKIE_HTTPONLY:", settings.CSRF_COOKIE_HTTPONLY)
print("SESSION_COOKIE_SECURE:", settings.SESSION_COOKIE_SECURE)
print("CSRF_COOKIE_SECURE:", settings.CSRF_COOKIE_SECURE)

print()
print("=" * 60)
print("SECTION 2 — APPS FANTOMES (en DB mais pas dans INSTALLED_APPS)")
print("=" * 60)
with connection.cursor() as c:
    c.execute("SELECT DISTINCT app FROM django_migrations ORDER BY app")
    db_apps = {r[0] for r in c.fetchall()}
installed = set(a.split('.')[-1] for a in settings.INSTALLED_APPS)
ghost_apps = db_apps - installed - {'admin', 'auth', 'contenttypes', 'sessions'}
print("Apps avec migrations en DB:", sorted(db_apps))
print("Apps dans INSTALLED_APPS:", sorted(installed))
print("Apps fantomes (tables orphelines):", sorted(ghost_apps))

print()
print("=" * 60)
print("SECTION 3 — INDEX MANQUANTS (hot paths)")
print("=" * 60)
with connection.cursor() as c:
    c.execute("""
        SELECT tablename, indexname
        FROM pg_indexes
        WHERE schemaname='public'
        AND tablename IN ('api_ruletrainingsample','api_trainingsample','api_trainingjob')
        ORDER BY tablename, indexname
    """)
    for r in c.fetchall():
        print(" ", r)
print()
print("Champ 'label' sur api_ruletrainingsample — index present?")
with connection.cursor() as c:
    c.execute("""
        SELECT indexname FROM pg_indexes
        WHERE tablename='api_ruletrainingsample'
        AND indexdef LIKE '%label%'
    """)
    rows = c.fetchall()
    print("  label index:", rows if rows else "ABSENT — requete filter(label__in=[...]) fait seq scan sur 69154 lignes")

print()
print("=" * 60)
print("SECTION 4 — DATASET COHERENCE")
print("=" * 60)
from api.models import RuleTrainingSample, TrainingSample, Document, Norme
from django.db.models import Count

total_rts = RuleTrainingSample.objects.count()
approved_rts = RuleTrainingSample.objects.filter(label='approved').count()
rejected_rts = RuleTrainingSample.objects.filter(label='rejected').count()
orphan_rts = RuleTrainingSample.objects.filter(document__isnull=True).count()
dupes = (RuleTrainingSample.objects
    .values('evidence_text', 'norm_id', 'rule_id', 'label')
    .annotate(c=Count('id'))
    .filter(c__gt=1)
    .count())

print(f"RuleTrainingSample: total={total_rts} approved={approved_rts} rejected={rejected_rts}")
print(f"  balance: {round(min(approved_rts,rejected_rts)/max(max(approved_rts,rejected_rts),1)*100,1)}%")
print(f"  orphans (no document): {orphan_rts}")
print(f"  duplicate groups (same evidence+norm+rule+label): {dupes}")

ts_total = TrainingSample.objects.count()
ts_appr = TrainingSample.objects.filter(label='approved').count()
ts_rej = TrainingSample.objects.filter(label='rejected').count()
ts_other = TrainingSample.objects.exclude(label__in=['approved','rejected']).count()
print(f"TrainingSample: total={ts_total} approved={ts_appr} rejected={ts_rej} other_labels={ts_other}")

doc_total = Document.objects.count()
doc_fin = Document.objects.filter(is_finalized=True).count()
print(f"Document: total={doc_total} finalized={doc_fin}")

print()
print("=== Per-norm breakdown ===")
for norm in Norme.objects.all():
    rts = RuleTrainingSample.objects.filter(norm=norm)
    ts = TrainingSample.objects.filter(standard=norm.name)
    rules_covered = rts.filter(label__in=['approved','rejected']).values('rule_id').distinct().count()
    total_rules = norm.rules.count()
    print(f"  {norm.name[:50]}")
    print(f"    RuleTS: {rts.count()} | approved={rts.filter(label='approved').count()} rejected={rts.filter(label='rejected').count()}")
    print(f"    TrainingS: {ts.count()} | rules covered: {rules_covered}/{total_rules}")

print()
print("=" * 60)
print("SECTION 5 — TESTS")
print("=" * 60)
import glob, ast
test_files = glob.glob('**/tests.py', recursive=True)
total_tests = 0
for tf in test_files:
    try:
        tree = ast.parse(open(tf).read())
        methods = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
        if methods:
            print(f"  {tf}: {len(methods)} tests — {methods}")
            total_tests += len(methods)
    except Exception as e:
        print(f"  {tf}: ERROR {e}")
print(f"TOTAL test methods: {total_tests}")

print()
print("=" * 60)
print("SECTION 6 — COMPOSANTS FRONTEND DUPLIQUES")
print("=" * 60)
import os
front = 'frontend/src/components'
if os.path.exists(front):
    files = os.listdir(front)
    print("Fichiers .js ET .jsx avec meme nom de base:")
    bases = {}
    for f in files:
        base = f.replace('.jsx','').replace('.js','')
        bases.setdefault(base, []).append(f)
    for base, flist in bases.items():
        if len(flist) > 1:
            print(f"  DUPLICATE: {flist}")

print()
print("=" * 60)
print("SECTION 7 — ML MODELS SUR DISQUE")
print("=" * 60)
import glob as g2
models_dir = 'ml/models'
pkls = g2.glob(os.path.join(models_dir, '*.pkl'))
jsons = g2.glob(os.path.join(models_dir, '*.json'))
print(f"PKL files: {len(pkls)}")
for f in sorted(pkls): print(f"  {os.path.basename(f)}")
print(f"JSON metrics files: {len(jsons)}")
for f in sorted(jsons): print(f"  {os.path.basename(f)}")

print()
print("=" * 60)
print("SECTION 8 — FAISS INDEX")
print("=" * 60)
faiss_files = g2.glob(os.path.join(models_dir, '*.faiss'))
npy_files = g2.glob(os.path.join(models_dir, '*.npy'))
meta_files = g2.glob(os.path.join(models_dir, '*.json'))
print("FAISS files:", [os.path.basename(f) for f in faiss_files])
print("NPY files:", [os.path.basename(f) for f in npy_files])
import json
for mf in meta_files:
    if 'meta' in mf:
        with open(mf) as f:
            data = json.load(f)
            if isinstance(data, list):
                print(f"FAISS meta entries: {len(data)}")
            elif isinstance(data, dict):
                print(f"FAISS meta keys: {list(data.keys())[:5]}")

print()
print("=" * 60)
print("SECTION 9 — MLOPS CONFIG STATE")
print("=" * 60)
from api.models import MLOpsConfig, TrainingJob
for cfg in MLOpsConfig.objects.all():
    print(f"  {cfg.standard}: last_trained={cfg.last_trained_at} f1={cfg.last_f1_score} version={cfg.current_model_version}")
print(f"TrainingJob records: {TrainingJob.objects.count()}")

print()
print("AUDIT COMPLETE")
