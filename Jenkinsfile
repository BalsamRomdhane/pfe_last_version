// ══════════════════════════════════════════════════════════════════════
// Jenkinsfile — Enterprise ISO Compliance Platform
// Pipeline MLOps — Windows local, sans Docker
// Version finale unique — Soutenance PFE + Démonstration Jenkins
//
// Basé sur lecture directe du dépôt :
//   ml/train_models.py           → train_all_models()      [training réel]
//   services/mlops_service.py    → compute_drift_score()   [drift réel]
//   services/mlops_service.py    → get_prometheus_metrics() [métriques réelles]
//   api/management/commands/     → system_audit, sync_all_datasets, fill_ml_datasets
//   api/models.py + migration 0014 → TrainingJob.log_output [champ confirmé]
//
// Stages :
//   1 · Checkout
//   2 · Install Dependencies
//   3 · Django Check & Migrate
//   4 · Dataset Validation
//   5 · Drift Detection          [compute_drift_score() — fonction réelle]
//   6 · ML Training              [train_all_models()    — fonction réelle]
//   7 · Export Métriques         [get_prometheus_metrics() + *_metrics.json]
//   8 · TrainingJob Update       [champs confirmés models.py + migration 0014]
// ══════════════════════════════════════════════════════════════════════

pipeline {
    agent any

    // ── Environnement ────────────────────────────────────────────────
    environment {
        BACKEND_DIR  = "${WORKSPACE}\\backend"
        FRONTEND_DIR = "${WORKSPACE}\\frontend"

        DJANGO_SETTINGS_MODULE = "enterprise_platform.settings"

        // Variables non-sensibles — modifier selon votre machine
        DB_HOST = "localhost"
        DB_PORT = "5432"
        DB_NAME = "compliance_db"
        DB_USER = "compliance_user"

        // Secrets uniquement dans Jenkins Credentials
        DB_PASSWORD            = credentials('DB_PASSWORD')
        DJANGO_SECRET_KEY      = credentials('DJANGO_SECRET_KEY')
        KEYCLOAK_CLIENT_SECRET = credentials('KEYCLOAK_CLIENT_SECRET')
    }

    // ── Paramètres de build ──────────────────────────────────────────
    parameters {
        choice(
            name: 'STANDARD',
            choices: ['ALL', 'ISO9001', 'ISO27001', 'TISAX'],
            description: 'Norme ISO à entraîner (ALL = les trois)'
        )
        booleanParam(
            name: 'FORCE_REGEN',
            defaultValue: false,
            description: 'Forcer la régénération des datasets synthétiques'
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
        stage('1 · Checkout') {
            steps {
                checkout scm
                bat 'git log --oneline -5'
                bat 'git status'
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 2 · Install Dependencies
        // Crée le venv si absent, installe requirements.txt,
        // vérifie les imports critiques.
        // ────────────────────────────────────────────────────────────
        stage('2 · Install Dependencies') {
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
        // manage.py check         : vérifie la configuration Django
        // manage.py migrate       : applique les migrations en attente
        //   + --run-syncdb        : crée les tables sans migration manquante
        // NOTE : --run-syncdb et --check ne peuvent PAS être combinés
        //        en Django 5.x (flags mutuellement exclusifs)
        // Vérifie ensuite que log_output existe sur TrainingJob
        //   (ajouté par migration 0014)
        // ────────────────────────────────────────────────────────────
        stage('3 · Django Check & Migrate') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat '.venv\\Scripts\\python.exe manage.py check'
                    bat '.venv\\Scripts\\python.exe manage.py migrate --run-syncdb'
                    bat '''
                        .venv\\Scripts\\python.exe -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()
from api.models import Norme, TrainingSample, RuleTrainingSample, TrainingJob, MLOpsConfig
fields = [f.name for f in TrainingJob._meta.get_fields()]
assert 'log_output' in fields, '[FAIL] TrainingJob.log_output absent — relancer: manage.py migrate'
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
        // Commandes réelles confirmées dans api/management/commands/ :
        //   system_audit        : aucun paramètre
        //   sync_all_datasets   : aucun paramètre requis
        //   fill_ml_datasets    : --seed INT | --force-regen | --dry-run
        // Vérifie ensuite que >= 20 samples labelisés existent.
        // ────────────────────────────────────────────────────────────
        stage('4 · Dataset Validation') {
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
    print('[FAIL] Insufficient samples (< 20) — pipeline aborted.')
    sys.exit(1)
print('[OK] Dataset valid:', total, 'labeled samples')
"
                    '''
                }
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 5 · Drift Detection
        // compute_drift_score(standard: str) → Dict
        // Confirmé dans services/mlops_service.py
        // Paramètre : nom EXACT de la norme tel qu'en base de données
        //   (ex: "ISO 9001 - Controle et validation des documents")
        //   → on itère sur Norme.objects.all() pour obtenir les vrais noms
        // Résultat sauvegardé dans artifacts/drift_report.json
        // ────────────────────────────────────────────────────────────
        stage('5 · Drift Detection') {
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
        // Confirmé dans ml/train_models.py ligne 614
        // C'est la SEULE fonction qui produit :
        //   RandomForest.pkl, LogisticRegression.pkl,
        //   GradientBoosting.pkl, BiLSTM.pkl, *_metrics.json
        //
        // IMPORTANT : train_compliance (ml/management/commands/) appelle
        //   compliance_service.retrain_models() → vectorize_rules()
        //   = vectorisation TF-IDF NLP, pas d'entraînement supervisé
        //   → ne pas utiliser pour générer les .pkl ML
        //
        // ISO27001 / TISAX : on cherche le nom réel en DB via __icontains
        //   pour correspondre aux noms longs ("ISO 27001 - ...") réellement
        //   stockés dans Norme.name
        // ────────────────────────────────────────────────────────────
        stage('6 · ML Training') {
            steps {
                dir("${BACKEND_DIR}") {
                    script {
                        def std = params.STANDARD

                        if (std == 'ALL' || std == 'ISO9001') {
                            bat '''
                                echo [TRAIN] ISO9001 — train_all_models()
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
                                echo [TRAIN] ISO27001 — train_all_models()
                                .venv\\Scripts\\python.exe -c "
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()
from api.models import Norme
norm = Norme.objects.filter(name__icontains='27001').first()
if not norm:
    print('[WARN] ISO27001 norm not found in DB — skipping.')
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
                                echo [TRAIN] TISAX — train_all_models()
                                .venv\\Scripts\\python.exe -c "
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()
from api.models import Norme
norm = Norme.objects.filter(name__icontains='tisax').first()
if not norm:
    print('[WARN] TISAX norm not found in DB — skipping.')
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
        // STAGE 7 · Export Métriques
        // get_prometheus_metrics() → str (format Prometheus text)
        //   confirmé dans services/mlops_service.py — aucun paramètre
        //   expose : compliance_documents_total, compliance_model_f1_score,
        //            compliance_drift_score, compliance_training_jobs_total
        //
        // *_metrics.json → lus depuis ml/models/ (générés par stage 6)
        //   format confirmé : { best_model, trained_at, samples, results{} }
        //   résultats affichés dans les logs Jenkins pour le jury
        // ────────────────────────────────────────────────────────────
        stage('7 · Export Métriques') {
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
        // Champs TrainingJob confirmés dans :
        //   api/models.py          : standard, status, start_time, end_time,
        //                            documents_count, new_docs_since,
        //                            drift_score, f1_score, precision_score,
        //                            recall_score, avg_similarity,
        //                            model_version, jenkins_build_id,
        //                            jenkins_url, triggered_by, drift_report
        //   migration 0014         : log_output (ajouté manuellement)
        // MLOpsConfig mis à jour simultanément (standard, last_trained_at,
        //   last_trained_doc_count, current_model_version, last_f1_score)
        // ────────────────────────────────────────────────────────────
        stage('8 · TrainingJob Update') {
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
    print('[WARN] No *_metrics.json found — training may have been skipped or failed.')
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

    }
    // ════════════════════════════════════════════════════════════════

    post {
        success {
            echo "✅ Pipeline SUCCESS — Build #${env.BUILD_NUMBER} | STANDARD=${params.STANDARD}"
        }
        failure {
            echo "❌ Pipeline FAILED  — Build #${env.BUILD_NUMBER} — Consulter les logs ci-dessus"
        }
        always {
            cleanWs(patterns: [[pattern: '**/__pycache__/**', type: 'INCLUDE'],
                               [pattern: '**/*.pyc',          type: 'INCLUDE']])
        }
    }
}
