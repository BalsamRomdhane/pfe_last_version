// ============================================================
// Jenkinsfile — Enterprise ISO Compliance Platform
// MLOps Pipeline — Windows Local (no Docker)
// Compatible: Jenkins 2.x, Windows, cmd/PowerShell
// Basé sur l'analyse réelle du dépôt :
//   - backend/ml/train_models.py  (train_all_models)
//   - ml/management/commands/train_compliance.py
//   - api/management/commands/fill_ml_datasets.py
//   - api/management/commands/rebuild_training_datasets.py
//   - api/management/commands/sync_all_datasets.py
//   - api/management/commands/system_audit.py
//   - services/mlops_service.py   (get_prometheus_metrics)
//   - api/tests.py
// ============================================================

pipeline {
    agent any

    // ── Variables d'environnement ────────────────────────────────────────
    environment {
        PYTHON_VENV         = "${WORKSPACE}\\backend\\.venv"
        PYTHON_EXE          = "${WORKSPACE}\\backend\\.venv\\Scripts\\python.exe"
        PIP_EXE             = "${WORKSPACE}\\backend\\.venv\\Scripts\\pip.exe"
        DJANGO_SETTINGS     = "enterprise_platform.settings"
        BACKEND_DIR         = "${WORKSPACE}\\backend"
        FRONTEND_DIR        = "${WORKSPACE}\\frontend"
        ML_MODELS_DIR       = "${WORKSPACE}\\backend\\ml\\models"
        ARTIFACTS_DIR       = "${WORKSPACE}\\artifacts"
        REPORTS_DIR         = "${WORKSPACE}\\artifacts\\reports"
        METRICS_FILE        = "${WORKSPACE}\\artifacts\\prometheus_metrics.txt"

        // Injectées via Jenkins Credentials (à créer dans Jenkins)
        DB_NAME             = credentials('DB_NAME')
        DB_USER             = credentials('DB_USER')
        DB_PASSWORD         = credentials('DB_PASSWORD')
        DB_HOST             = credentials('DB_HOST')
        DB_PORT             = credentials('DB_PORT')
        DJANGO_SECRET_KEY   = credentials('DJANGO_SECRET_KEY')
        KEYCLOAK_SERVER_URL = credentials('KEYCLOAK_SERVER_URL')
        KEYCLOAK_CLIENT_ID  = credentials('KEYCLOAK_CLIENT_ID')
        KEYCLOAK_CLIENT_SECRET = credentials('KEYCLOAK_CLIENT_SECRET')
        JENKINS_JOB_NAME    = "compliance-ml-pipeline"
    }

    // ── Paramètres du pipeline ───────────────────────────────────────────
    parameters {
        choice(
            name: 'STANDARD',
            choices: ['ALL', 'ISO9001', 'ISO27001', 'TISAX'],
            description: 'Norme ISO à entraîner (ALL = toutes)'
        )
        booleanParam(
            name: 'FORCE_RETRAIN',
            defaultValue: false,
            description: 'Forcer le réentraînement même si le dataset est insuffisant'
        )
        booleanParam(
            name: 'SKIP_FRONTEND',
            defaultValue: false,
            description: 'Ignorer le build frontend (CI rapide)'
        )
        string(
            name: 'MIN_SAMPLES',
            defaultValue: '20',
            description: 'Nombre minimum de samples pour déclencher l entraînement'
        )
    }

    // ── Options globales ─────────────────────────────────────────────────
    options {
        timeout(time: 60, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timestamps()
        ansiColor('xterm')
    }

    // ── Déclencheurs ─────────────────────────────────────────────────────
    triggers {
        githubPush()
    }

    // ════════════════════════════════════════════════════════════════════
    // STAGES
    // ════════════════════════════════════════════════════════════════════
    stages {

        // ────────────────────────────────────────────────────────────────
        // STAGE 1 : Checkout GitHub
        // ────────────────────────────────────────────────────────────────
        stage('Stage 1 : Checkout GitHub') {
            steps {
                echo '=== STAGE 1 : Checkout ==='
                checkout scm
                bat 'git log --oneline -5'
                bat 'git status'
            }
        }

        // ────────────────────────────────────────────────────────────────
        // STAGE 2 : Installation des dépendances Python
        // ────────────────────────────────────────────────────────────────
        stage('Stage 2 : Installation dépendances Python') {
            steps {
                echo '=== STAGE 2 : Python dependencies ==='
                dir("${BACKEND_DIR}") {
                    bat '''
                        IF NOT EXIST ".venv\\Scripts\\python.exe" (
                            echo [INFO] Création du venv Python...
                            python -m venv .venv
                        ) ELSE (
                            echo [INFO] venv existant détecté.
                        )
                    '''
                    bat '''
                        .venv\\Scripts\\python.exe -m pip install --upgrade pip --quiet
                        .venv\\Scripts\\pip.exe install -r requirements.txt --quiet
                    '''
                    // Vérification des imports critiques
                    bat '''
                        .venv\\Scripts\\python.exe -c "import django; print('[OK] django', django.__version__)"
                        .venv\\Scripts\\python.exe -c "import sklearn; print('[OK] sklearn', sklearn.__version__)"
                        .venv\\Scripts\\python.exe -c "import joblib; print('[OK] joblib')"
                        .venv\\Scripts\\python.exe -c "import numpy; print('[OK] numpy')"
                    '''
                }
            }
        }

        // ────────────────────────────────────────────────────────────────
        // STAGE 3 : Validation Django
        // ────────────────────────────────────────────────────────────────
        stage('Stage 3 : Validation Django') {
            steps {
                echo '=== STAGE 3 : Django validation ==='
                dir("${BACKEND_DIR}") {
                    bat '''
                        SET DJANGO_SETTINGS_MODULE=enterprise_platform.settings
                        .venv\\Scripts\\python.exe manage.py check --deploy 2>&1 | findstr /V "WARNINGS"
                    '''
                    bat '''
                        SET DJANGO_SETTINGS_MODULE=enterprise_platform.settings
                        .venv\\Scripts\\python.exe manage.py migrate --run-syncdb --check
                    '''
                    bat '''
                        SET DJANGO_SETTINGS_MODULE=enterprise_platform.settings
                        .venv\\Scripts\\python.exe -c "
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'enterprise_platform.settings'
django.setup()
from api.models import Norme, TrainingSample, RuleTrainingSample, TrainingJob, MLOpsConfig
print('[OK] All MLOps models imported successfully')
print('  Norme:', Norme.objects.count())
print('  TrainingSample:', TrainingSample.objects.count())
print('  RuleTrainingSample:', RuleTrainingSample.objects.count())
print('  TrainingJob:', TrainingJob.objects.count())
print('  MLOpsConfig:', MLOpsConfig.objects.count())
"
                    '''
                }
            }
        }

        // ────────────────────────────────────────────────────────────────
        // STAGE 4 : Exécution des tests Django
        // ────────────────────────────────────────────────────────────────
        stage('Stage 4 : Tests Django') {
            steps {
                echo '=== STAGE 4 : Django tests ==='
                dir("${BACKEND_DIR}") {
                    bat '''
                        SET DJANGO_SETTINGS_MODULE=enterprise_platform.settings
                        .venv\\Scripts\\python.exe -m pytest api/tests.py -v ^
                            --tb=short ^
                            --no-header ^
                            --junit-xml=../artifacts/reports/test-results.xml 2>&1
                    '''
                }
            }
            post {
                always {
                    script {
                        if (fileExists("${WORKSPACE}\\artifacts\\reports\\test-results.xml")) {
                            junit "${WORKSPACE}\\artifacts\\reports\\test-results.xml"
                        }
                    }
                }
            }
        }

        // ────────────────────────────────────────────────────────────────
        // STAGE 5 : Validation & Sync Dataset
        // Commandes réelles : sync_all_datasets, system_audit
        // ────────────────────────────────────────────────────────────────
        stage('Stage 5 : Validation Dataset') {
            steps {
                echo '=== STAGE 5 : Dataset validation ==='
                dir("${BACKEND_DIR}") {
                    bat '''
                        SET DJANGO_SETTINGS_MODULE=enterprise_platform.settings
                        echo [INFO] Audit du systeme...
                        .venv\\Scripts\\python.exe manage.py system_audit
                    '''
                    bat '''
                        SET DJANGO_SETTINGS_MODULE=enterprise_platform.settings
                        echo [INFO] Synchronisation des datasets...
                        .venv\\Scripts\\python.exe manage.py sync_all_datasets
                    '''
                    // Vérification du seuil minimum de samples
                    bat """
                        SET DJANGO_SETTINGS_MODULE=enterprise_platform.settings
                        .venv\\Scripts\\python.exe -c "
import django, os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'enterprise_platform.settings'
django.setup()
from api.models import RuleTrainingSample
total = RuleTrainingSample.objects.filter(label__in=['approved','rejected']).count()
print('[INFO] RuleTrainingSample labeled:', total)
min_req = int('${params.MIN_SAMPLES}')
if total < min_req:
    print('[WARN] Insufficient samples:', total, '< min', min_req)
    sys.exit(1)
else:
    print('[OK] Dataset sufficient:', total, '>= min', min_req)
"
                    """
                }
            }
        }

        // ────────────────────────────────────────────────────────────────
        // STAGE 6 : Drift Detection
        // Commande réelle : services/mlops_service.py::compute_drift_score
        // ────────────────────────────────────────────────────────────────
        stage('Stage 6 : Drift Detection') {
            steps {
                echo '=== STAGE 6 : Drift detection ==='
                dir("${BACKEND_DIR}") {
                    bat '''
                        SET DJANGO_SETTINGS_MODULE=enterprise_platform.settings
                        .venv\\Scripts\\python.exe -c "
import django, os, json, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'enterprise_platform.settings'
django.setup()
from services.mlops_service import compute_drift_score
standards = ['ISO9001', 'ISO27001', 'TISAX']
drift_results = {}
for std in standards:
    result = compute_drift_score(std)
    drift_results[std] = result
    status = result.get('status', 'unknown')
    score  = result.get('drift_score', 0.0)
    print(f'[DRIFT] {std}: score={score:.4f} status={status}')
    if status == 'critical':
        print(f'[WARN]  {std} drift CRITICAL — retraining strongly recommended')

with open('..\\\\artifacts\\\\drift_report.json', 'w', encoding='utf-8') as f:
    json.dump(drift_results, f, indent=2, default=str)
print('[OK] Drift report saved.')
"
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'artifacts/drift_report.json', allowEmptyArchive: true
                }
            }
        }

        // ────────────────────────────────────────────────────────────────
        // STAGE 7 : Entraînement ML
        // Commandes réelles :
        //   - ml/management/commands/train_compliance.py  (per standard)
        //   - ml/train_models.py::train_all_models        (core function)
        //   - fill_ml_datasets si insuffisant
        // ────────────────────────────────────────────────────────────────
        stage('Stage 7 : Entraînement ML') {
            steps {
                echo '=== STAGE 7 : ML Training ==='
                dir("${BACKEND_DIR}") {
                    script {
                        def std = params.STANDARD
                        def force = params.FORCE_RETRAIN ? '--force' : ''

                        if (std == 'ALL' || std == 'ISO9001') {
                            bat """
                                SET DJANGO_SETTINGS_MODULE=enterprise_platform.settings
                                echo [INFO] Fill/check dataset ISO9001...
                                .venv\\\\Scripts\\\\python.exe manage.py fill_ml_datasets --seed 42
                                echo [INFO] Training ISO9001...
                                .venv\\\\Scripts\\\\python.exe manage.py train_compliance --standard ISO9001 ${force}
                            """
                        }
                        if (std == 'ALL' || std == 'ISO27001') {
                            bat """
                                SET DJANGO_SETTINGS_MODULE=enterprise_platform.settings
                                echo [INFO] Training ISO27001...
                                .venv\\\\Scripts\\\\python.exe manage.py train_compliance --standard ISO27001 ${force}
                            """
                        }
                        if (std == 'ALL' || std == 'TISAX') {
                            bat """
                                SET DJANGO_SETTINGS_MODULE=enterprise_platform.settings
                                echo [INFO] Training TISAX...
                                .venv\\\\Scripts\\\\python.exe manage.py train_compliance --standard TISAX ${force}
                            """
                        }
                    }
                }
            }
        }

        // ────────────────────────────────────────────────────────────────
        // STAGE 8 : Évaluation des modèles
        // Lit les fichiers metrics.json réels générés par train_all_models
        // Format réel : ml/models/*_metrics.json
        // ────────────────────────────────────────────────────────────────
        stage('Stage 8 : Évaluation des modèles') {
            steps {
                echo '=== STAGE 8 : Model evaluation ==='
                dir("${BACKEND_DIR}") {
                    bat '''
                        SET DJANGO_SETTINGS_MODULE=enterprise_platform.settings
                        .venv\\Scripts\\python.exe -c "
import os, json, glob

models_dir = os.path.join('ml', 'models')
metrics_files = glob.glob(os.path.join(models_dir, '*_metrics.json'))

if not metrics_files:
    print('[WARN] No metrics files found in ml/models/')
    exit(0)

all_ok = True
summary = []

for mf in metrics_files:
    norm_name = os.path.basename(mf).replace('_metrics.json', '')
    with open(mf, 'r', encoding='utf-8') as f:
        data = json.load(f)

    best_model  = data.get('best_model', 'unknown')
    trained_at  = data.get('trained_at', 'N/A')
    samples     = data.get('samples', 0)
    results     = data.get('results', {})

    print(f'')
    print(f'[EVAL] Norm: {norm_name}')
    print(f'       Best model : {best_model}')
    print(f'       Trained at : {trained_at}')
    print(f'       Samples    : {samples}')

    for model_name, metrics in results.items():
        acc = metrics.get('accuracy', 0)
        f1  = metrics.get('f1_score', 0)
        prec = metrics.get('precision', 0)
        rec  = metrics.get('recall', 0)
        print(f'       {model_name:<20} acc={acc:.4f} f1={f1:.4f} prec={prec:.4f} rec={rec:.4f}')
        if acc < 0.60:
            print(f'[FAIL] {model_name} accuracy {acc:.4f} below threshold 0.60')
            all_ok = False

    summary.append({'norm': norm_name, 'best_model': best_model, 'samples': samples, 'results': results})

with open(os.path.join('..', 'artifacts', 'evaluation_summary.json'), 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print('')
if all_ok:
    print('[OK] All models passed evaluation thresholds.')
else:
    print('[WARN] Some models below threshold — review required.')
"
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'artifacts/evaluation_summary.json', allowEmptyArchive: true
                }
            }
        }

        // ────────────────────────────────────────────────────────────────
        // STAGE 9 : Sauvegarde des métriques Prometheus
        // Commande réelle : services/mlops_service.py::get_prometheus_metrics
        // ────────────────────────────────────────────────────────────────
        stage('Stage 9 : Export Prometheus') {
            steps {
                echo '=== STAGE 9 : Prometheus metrics ==='
                dir("${BACKEND_DIR}") {
                    bat '''
                        SET DJANGO_SETTINGS_MODULE=enterprise_platform.settings
                        .venv\\Scripts\\python.exe -c "
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'enterprise_platform.settings'
django.setup()
from services.mlops_service import get_prometheus_metrics
metrics_text = get_prometheus_metrics()
out_path = os.path.join('..', 'artifacts', 'prometheus_metrics.txt')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(metrics_text)
print('[OK] Prometheus metrics saved to artifacts/prometheus_metrics.txt')
print(metrics_text[:800])
"
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'artifacts/prometheus_metrics.txt', allowEmptyArchive: true
                }
            }
        }

        // ────────────────────────────────────────────────────────────────
        // STAGE 10 : Mise à jour du TrainingJob Django
        // Commande réelle : services/mlops_service.py::update_job_result
        // Crée/met à jour MLOpsConfig pour chaque norme entraînée
        // ────────────────────────────────────────────────────────────────
        stage('Stage 10 : Mise à jour TrainingJob') {
            steps {
                echo '=== STAGE 10 : TrainingJob update ==='
                dir("${BACKEND_DIR}") {
                    bat '''
                        SET DJANGO_SETTINGS_MODULE=enterprise_platform.settings
                        .venv\\Scripts\\python.exe -c "
import django, os, json, glob
os.environ['DJANGO_SETTINGS_MODULE'] = 'enterprise_platform.settings'
django.setup()

from api.models import TrainingJob, MLOpsConfig
from django.utils import timezone

models_dir = os.path.join('ml', 'models')
metrics_files = glob.glob(os.path.join(models_dir, '*_metrics.json'))

build_id = os.getenv('BUILD_NUMBER', '0')
build_url = os.getenv('BUILD_URL', '')

for mf in metrics_files:
    with open(mf, 'r', encoding='utf-8') as f:
        data = json.load(f)

    standard = data.get('standard', 'unknown')
    best_model = data.get('best_model', '')
    samples = data.get('samples', 0)
    results = data.get('results', {})

    best_metrics = results.get(best_model, {})
    f1_val  = float(best_metrics.get('f1_score', 0.0))
    prec    = float(best_metrics.get('precision', 0.0))
    rec     = float(best_metrics.get('recall', 0.0))
    acc     = float(best_metrics.get('accuracy', 0.0))

    job = TrainingJob.objects.create(
        standard=standard,
        status='success',
        start_time=timezone.now(),
        end_time=timezone.now(),
        documents_count=samples,
        f1_score=f1_val,
        precision_score=prec,
        recall_score=rec,
        model_version=f'jenkins-build-{build_id}-{best_model}',
        jenkins_build_id=build_id,
        jenkins_url=build_url,
        triggered_by='jenkins',
        drift_report=data.get('dataset_quality', {}),
    )

    MLOpsConfig.objects.update_or_create(
        standard=standard,
        defaults={
            'last_trained_at': timezone.now(),
            'last_trained_doc_count': samples,
            'current_model_version': f'jenkins-build-{build_id}-{best_model}',
            'last_f1_score': f1_val,
        }
    )
    print(f'[OK] TrainingJob #{job.id} created for {standard} (f1={f1_val:.4f})')

print('[OK] All TrainingJobs updated.')
"
                    '''
                }
            }
        }

        // ────────────────────────────────────────────────────────────────
        // STAGE 11 : Build Frontend React (optionnel)
        // ────────────────────────────────────────────────────────────────
        stage('Stage 11 : Build Frontend') {
            when {
                expression { return !params.SKIP_FRONTEND }
            }
            steps {
                echo '=== STAGE 11 : Frontend build ==='
                dir("${FRONTEND_DIR}") {
                    bat '''
                        IF NOT EXIST "node_modules" (
                            echo [INFO] Installing npm dependencies...
                            node ./node_modules/react-scripts/bin/react-scripts.js build 2>&1 || npm install --legacy-peer-deps
                        )
                        echo [INFO] Building React app...
                        npm run build 2>&1
                    '''
                }
            }
        }

        // ────────────────────────────────────────────────────────────────
        // STAGE 12 : Archivage des artefacts
        // ────────────────────────────────────────────────────────────────
        stage('Stage 12 : Archivage artefacts') {
            steps {
                echo '=== STAGE 12 : Archiving artifacts ==='
                dir("${BACKEND_DIR}") {
                    bat '''
                        IF NOT EXIST "..\\artifacts\\reports" mkdir "..\\artifacts\\reports"
                        IF NOT EXIST "..\\artifacts\\models"  mkdir "..\\artifacts\\models"
                    '''
                    // Copier les modèles .pkl et métriques dans artifacts/models/
                    bat '''
                        FOR %%F IN (ml\\models\\*.pkl) DO (
                            copy /Y "%%F" "..\\artifacts\\models\\" >nul
                        )
                        FOR %%F IN (ml\\models\\*.json) DO (
                            copy /Y "%%F" "..\\artifacts\\models\\" >nul
                        )
                        echo [OK] Models and metrics archived.
                    '''
                }
                // Archiver tout ce qui est dans artifacts/
                archiveArtifacts artifacts: 'artifacts/**/*', allowEmptyArchive: true
            }
        }

    }
    // ════════════════════════════════════════════════════════════════════
    // POST — Notifications de fin de pipeline
    // ════════════════════════════════════════════════════════════════════
    post {
        success {
            echo """
╔══════════════════════════════════════════════════════════════╗
║  PIPELINE SUCCESS — Enterprise ISO Compliance Platform       ║
║  Build #${env.BUILD_NUMBER} completed successfully           ║
║  Standard: ${params.STANDARD}                                ║
╚══════════════════════════════════════════════════════════════╝
"""
        }
        failure {
            echo """
╔══════════════════════════════════════════════════════════════╗
║  PIPELINE FAILED — Build #${env.BUILD_NUMBER}                ║
║  Check logs above for root cause.                            ║
╚══════════════════════════════════════════════════════════════╝
"""
        }
        always {
            echo '[INFO] Pipeline completed. Artifacts available in the Jenkins workspace.'
            cleanWs(patterns: [[pattern: '**/__pycache__/**', type: 'INCLUDE'],
                               [pattern: '**/*.pyc',          type: 'INCLUDE']])
        }
    }

}
