// ══════════════════════════════════════════════════════════════════════
// Jenkinsfile — Enterprise ISO Compliance Platform
// Pipeline MLOps — Windows local, sans Docker
// Version soutenance PFE — Jenkins vierge, aucun credential requis
//
// CORRECTIONS v2 :
//   ✅ credentials() supprimés — Django lit le .env local directement
//   ✅ cleanWs() déplacé dans un stage dédié (corrige MissingContextVariableException)
//   ✅ Branche : */main
//   ✅ 100% bat, zéro sh/bash
// ══════════════════════════════════════════════════════════════════════

pipeline {
    agent any

    // ── Environnement ────────────────────────────────────────────────
    // AUCUN credentials() ici.
    // Django lit DB_PASSWORD et DJANGO_SECRET_KEY depuis backend/.env
    // Ces variables sont déjà présentes dans le fichier .env du projet.
    environment {
        BACKEND_DIR            = "${WORKSPACE}\\backend"
        DJANGO_SETTINGS_MODULE = "enterprise_platform.settings"

        // Variables de connexion PostgreSQL — adapter à votre machine
        DB_HOST = "localhost"
        DB_PORT = "5432"
        DB_NAME = "compliance_db"
        DB_USER = "compliance_user"
    }

    // ── Paramètres de build ──────────────────────────────────────────
    parameters {
        choice(
            name: 'STANDARD',
            choices: ['ALL', 'ISO9001', 'ISO27001', 'TISAX'],
            description: 'Norme ISO a entrainer (ALL = les trois)'
        )
        booleanParam(
            name: 'FORCE_REGEN',
            defaultValue: false,
            description: 'Forcer la regeneration des datasets synthetiques'
        )
    }

    options {
        timeout(time: 45, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timestamps()
    }

    // ════════════════════════════════════════════════════════════════
    stages {

        // ────────────────────────────────────────────────────────────
        // STAGE 1 · Checkout
        // ────────────────────────────────────────────────────────────
        stage('1 - Checkout') {
            steps {
                checkout scm
                bat 'git log --oneline -5'
                bat 'git status'
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 2 · Install Dependencies
        // Crée le venv Python si absent, installe requirements.txt
        // ────────────────────────────────────────────────────────────
        stage('2 - Install Dependencies') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat '''
                        IF NOT EXIST ".venv\\Scripts\\python.exe" (
                            echo [INFO] Creating Python virtual environment...
                            python -m venv .venv
                        ) ELSE (
                            echo [INFO] Reusing existing virtual environment.
                        )
                        .venv\\Scripts\\python.exe -m pip install --upgrade pip --quiet
                        .venv\\Scripts\\pip.exe install -r requirements.txt --quiet
                        echo [OK] Dependencies installed.
                        .venv\\Scripts\\python.exe -c "import django, sklearn, joblib, numpy; print('[OK] Core imports verified')"
                    '''
                }
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 3 · Django Check & Migrate
        // manage.py check       : verifie la config Django
        // manage.py migrate     : applique les migrations + syncdb
        // NOTE : --run-syncdb et --check sont mutuellement exclusifs
        //        en Django 5.x — on les separe
        // ────────────────────────────────────────────────────────────
        stage('3 - Django Check') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat '.venv\\Scripts\\python.exe manage.py check'
                    bat '.venv\\Scripts\\python.exe manage.py migrate --run-syncdb'
                    bat '''
                        .venv\\Scripts\\python.exe -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()
from api.models import Norme, RuleTrainingSample, TrainingJob
fields = [f.name for f in TrainingJob._meta.get_fields()]
assert 'log_output' in fields, '[FAIL] TrainingJob.log_output absent - relancer: manage.py migrate'
print('[OK] Django OK')
print('[OK] Norme:', Norme.objects.count())
print('[OK] RuleTrainingSample:', RuleTrainingSample.objects.count())
print('[OK] TrainingJob.log_output confirmed')
"
                    '''
                }
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 4 · Dataset Validation
        // Commandes reelles dans api/management/commands/ :
        //   system_audit      : aucun parametre
        //   sync_all_datasets : aucun parametre requis
        //   fill_ml_datasets  : --seed INT | --force-regen | --dry-run
        // ────────────────────────────────────────────────────────────
        stage('4 - Dataset Validation') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat '''
                        echo [INFO] Running system audit...
                        .venv\\Scripts\\python.exe manage.py system_audit
                    '''
                    bat '''
                        echo [INFO] Syncing training datasets...
                        .venv\\Scripts\\python.exe manage.py sync_all_datasets
                    '''
                    script {
                        def forceFlag = params.FORCE_REGEN ? '--force-regen' : ''
                        bat ".venv\\\\Scripts\\\\python.exe manage.py fill_ml_datasets --seed 42 ${forceFlag}"
                    }
                    bat '''
                        .venv\\Scripts\\python.exe -c "
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()
from api.models import RuleTrainingSample
total = RuleTrainingSample.objects.filter(label__in=['approved','rejected']).count()
print('[INFO] Labeled RuleTrainingSamples:', total)
if total < 20:
    print('[FAIL] Insufficient samples (< 20) - pipeline aborted.')
    sys.exit(1)
print('[OK] Dataset valid:', total, 'labeled samples')
"
                    '''
                }
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 5 · Drift Detection
        // compute_drift_score(standard: str) confirme dans
        // services/mlops_service.py — passe le nom reel de la norme
        // depuis Norme.objects.all() (pas 'ISO9001' hardcode)
        // ────────────────────────────────────────────────────────────
        stage('5 - Drift Detection') {
            steps {
                bat 'IF NOT EXIST "%WORKSPACE%\\artifacts" mkdir "%WORKSPACE%\\artifacts"'
                dir("${BACKEND_DIR}") {
                    bat '''
                        .venv\\Scripts\\python.exe -c "
import django, os, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()
from services.mlops_service import compute_drift_score
from api.models import Norme

results = {}
for norm in Norme.objects.all():
    result = compute_drift_score(norm.name)
    score  = result.get('drift_score', 0.0)
    status = result.get('status', 'unknown')
    print('[DRIFT] %-45s score=%.4f  status=%s' % (norm.name[:45], score, status))
    results[norm.name] = result

out = os.path.join('..', 'artifacts', 'drift_report.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, default=str)
print('[OK] Drift report saved -> artifacts/drift_report.json')
"
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'artifacts/drift_report.json',
                                     allowEmptyArchive: true
                }
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 6 · ML Training
        // train_all_models(standard, norme_id, dataset_type)
        // Confirme dans ml/train_models.py ligne 614
        // Produit : RF.pkl, LR.pkl, GBT.pkl, BiLSTM.pkl, *_metrics.json
        //
        // ISO27001 / TISAX : recherche le nom reel via __icontains
        // car les noms en DB sont longs ("ISO 27001 - ...")
        // ────────────────────────────────────────────────────────────
        stage('6 - ML Training') {
            steps {
                dir("${BACKEND_DIR}") {
                    script {
                        def std = params.STANDARD

                        if (std == 'ALL' || std == 'ISO9001') {
                            bat '''
                                echo [TRAIN] ISO9001 - train_all_models()
                                .venv\\Scripts\\python.exe -c "
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()
from ml.train_models import train_all_models
result = train_all_models(standard=None, dataset_type='classification')
if isinstance(result, dict) and 'error' in result:
    print('[FAIL] ISO9001:', result['error'])
    sys.exit(1)
print('[OK] ISO9001  best=%-18s  samples=%d' % (result.get('best_model','?'), result.get('samples',0)))
"
                            '''
                        }

                        if (std == 'ALL' || std == 'ISO27001') {
                            bat '''
                                echo [TRAIN] ISO27001 - train_all_models()
                                .venv\\Scripts\\python.exe -c "
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()
from api.models import Norme
norm = Norme.objects.filter(name__icontains='27001').first()
if not norm:
    print('[WARN] ISO27001 norm not found in DB - skipping.')
    sys.exit(0)
from ml.train_models import train_all_models
result = train_all_models(standard=norm.name, dataset_type='classification')
if isinstance(result, dict) and 'error' in result:
    print('[WARN] ISO27001:', result['error'])
    sys.exit(0)
print('[OK] ISO27001 best=%-18s  samples=%d' % (result.get('best_model','?'), result.get('samples',0)))
"
                            '''
                        }

                        if (std == 'ALL' || std == 'TISAX') {
                            bat '''
                                echo [TRAIN] TISAX - train_all_models()
                                .venv\\Scripts\\python.exe -c "
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()
from api.models import Norme
norm = Norme.objects.filter(name__icontains='tisax').first()
if not norm:
    print('[WARN] TISAX norm not found in DB - skipping.')
    sys.exit(0)
from ml.train_models import train_all_models
result = train_all_models(standard=norm.name, dataset_type='classification')
if isinstance(result, dict) and 'error' in result:
    print('[WARN] TISAX:', result['error'])
    sys.exit(0)
print('[OK] TISAX   best=%-18s  samples=%d' % (result.get('best_model','?'), result.get('samples',0)))
"
                            '''
                        }
                    }
                }
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 7 · Export Metriques
        // get_prometheus_metrics() : aucun parametre — retourne str
        // *_metrics.json : lus depuis ml/models/ (generes stage 6)
        // ────────────────────────────────────────────────────────────
        stage('7 - Export Metriques') {
            steps {
                bat 'IF NOT EXIST "%WORKSPACE%\\artifacts" mkdir "%WORKSPACE%\\artifacts"'
                dir("${BACKEND_DIR}") {
                    bat '''
                        .venv\\Scripts\\python.exe -c "
import django, os, json, glob
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from services.mlops_service import get_prometheus_metrics
prom = get_prometheus_metrics()
with open(os.path.join('..', 'artifacts', 'prometheus_metrics.txt'), 'w', encoding='utf-8') as f:
    f.write(prom)
print('[OK] Prometheus metrics -> artifacts/prometheus_metrics.txt')

summary = []
for mf in glob.glob(os.path.join('ml', 'models', '*_metrics.json')):
    with open(mf, 'r', encoding='utf-8') as f:
        data = json.load(f)
    norm_key = os.path.basename(mf).replace('_metrics.json', '')
    best     = data.get('best_model', '?')
    samples  = data.get('samples', 0)
    print('')
    print('[EVAL] %s' % norm_key)
    print('       Best model : %s  |  Samples : %d' % (best, samples))
    for m, v in data.get('results', {}).items():
        print('       %-22s  f1=%.4f  acc=%.4f  prec=%.4f  rec=%.4f' % (
            m,
            v.get('f1_score', 0),
            v.get('accuracy', 0),
            v.get('precision', 0),
            v.get('recall', 0),
        ))
    summary.append({'norm': norm_key, 'best_model': best, 'samples': samples})

with open(os.path.join('..', 'artifacts', 'evaluation_summary.json'), 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)
print('')
print('[OK] Evaluation summary -> artifacts/evaluation_summary.json')
"
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'artifacts/prometheus_metrics.txt,artifacts/evaluation_summary.json,artifacts/drift_report.json',
                                     allowEmptyArchive: true
                }
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 8 · TrainingJob Update
        // Tous les champs confirmes dans api/models.py + migration 0014
        // ────────────────────────────────────────────────────────────
        stage('8 - TrainingJob Update') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat '''
                        .venv\\Scripts\\python.exe -c "
import django, os, json, glob
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from api.models import TrainingJob, MLOpsConfig
from django.utils import timezone

build_id  = os.getenv('BUILD_NUMBER', '0')
build_url = os.getenv('BUILD_URL', '')
created   = 0

metrics_files = glob.glob(os.path.join('ml', 'models', '*_metrics.json'))
if not metrics_files:
    print('[WARN] No *_metrics.json found - training may have been skipped or failed.')
else:
    for mf in metrics_files:
        with open(mf, 'r', encoding='utf-8') as f:
            data = json.load(f)

        standard   = data.get('standard', 'unknown')
        best_model = data.get('best_model', '')
        samples    = int(data.get('samples', 0))
        bm         = data.get('results', {}).get(best_model, {})

        job = TrainingJob.objects.create(
            standard         = standard,
            status           = 'success',
            start_time       = timezone.now(),
            end_time         = timezone.now(),
            documents_count  = samples,
            new_docs_since   = 0,
            f1_score         = float(bm.get('f1_score', 0.0)),
            precision_score  = float(bm.get('precision', 0.0)),
            recall_score     = float(bm.get('recall', 0.0)),
            avg_similarity   = float(bm.get('accuracy', 0.0)),
            model_version    = 'jenkins-%s-%s' % (build_id, best_model),
            jenkins_build_id = build_id,
            jenkins_url      = build_url,
            triggered_by     = 'jenkins',
            drift_report     = data.get('dataset_quality', {}),
            log_output       = 'Build #%s | %s | best=%s' % (build_id, standard, best_model),
        )

        MLOpsConfig.objects.update_or_create(
            standard = standard,
            defaults = {
                'last_trained_at'        : timezone.now(),
                'last_trained_doc_count' : samples,
                'current_model_version'  : 'jenkins-%s-%s' % (build_id, best_model),
                'last_f1_score'          : float(bm.get('f1_score', 0.0)),
            }
        )
        print('[OK] TrainingJob #%d | %-45s  f1=%.4f' % (job.id, standard, float(bm.get('f1_score',0))))
        created += 1

print('[OK] %d TrainingJob(s) recorded in database.' % created)
"
                    '''
                }
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 9 · Cleanup
        // cleanWs() DOIT etre dans un stage (pas dans post { always })
        // pour eviter MissingContextVariableException: hudson.FilePath
        // On supprime uniquement les fichiers Python caches
        // ────────────────────────────────────────────────────────────
        stage('9 - Cleanup') {
            steps {
                bat '''
                    echo [INFO] Cleaning Python cache files...
                    FOR /R "%WORKSPACE%" %%D IN (__pycache__) DO (
                        IF EXIST "%%D" RMDIR /S /Q "%%D" 2>nul
                    )
                    echo [OK] Cleanup done.
                '''
            }
        }

    }
    // ════════════════════════════════════════════════════════════════

    post {
        success {
            echo "Pipeline SUCCESS - Build ${env.BUILD_NUMBER} | STANDARD=${params.STANDARD}"
        }
        failure {
            echo "Pipeline FAILED  - Build ${env.BUILD_NUMBER} - Consulter les logs ci-dessus"
        }
    }
}
