// ══════════════════════════════════════════════════════════════════════
// Jenkinsfile — Enterprise ISO Compliance Platform
// Pipeline MLOps — Windows local, sans Docker
// Version finale — 100% compatible CMD Windows
//
// ARCHITECTURE :
//   Tout le code Python multi-lignes est dans backend/ci/*.py
//   Les stages bat n'appellent que des commandes simples sur une ligne
//   Aucun bloc python -c "..." multi-lignes dans ce fichier
// ══════════════════════════════════════════════════════════════════════

pipeline {
    agent any

    environment {
        BACKEND_DIR            = "${WORKSPACE}\\backend"
        DJANGO_SETTINGS_MODULE = "enterprise_platform.settings"

        // UTF-8 force — obligatoire Windows CP850/CP1252
        PYTHONIOENCODING = "utf-8"
        PYTHONUTF8       = "1"

        // PostgreSQL — adapter selon votre machine
        DB_HOST = "localhost"
        DB_PORT = "5432"
        DB_NAME = "compliance_db"
        DB_USER = "postgres"
    }

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
                bat 'chcp 65001 > nul && git log --oneline -5'
                bat 'chcp 65001 > nul && git status'
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 2 · Install Dependencies
        // ────────────────────────────────────────────────────────────
        stage('2 - Install Dependencies') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat '''
                        chcp 65001 > nul
                        IF NOT EXIST ".venv\\Scripts\\python.exe" (
                            echo [INFO] Creating Python virtual environment...
                            python -m venv .venv
                        ) ELSE (
                            echo [INFO] Reusing existing virtual environment.
                        )
                    '''
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe -m pip install --upgrade pip --quiet'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\pip.exe install -r requirements.txt --quiet'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe -c "import django"'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe -c "import sklearn"'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe -c "import joblib"'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe -c "import numpy"'
                    bat 'echo [OK] Core imports verified'
                }
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 3 · Django Check & Migrate
        // Scripts : ci/check_django.py
        // ────────────────────────────────────────────────────────────
        stage('3 - Django Check') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py check'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py migrate'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\check_django.py'
                }
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 4 · Dataset Validation
        // Scripts : ci/check_dataset.py
        // Commandes : system_audit, sync_all_datasets, fill_ml_datasets
        // ────────────────────────────────────────────────────────────
        stage('4 - Dataset Validation') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py system_audit || echo [WARN] system_audit exited with non-zero but continuing'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py sync_all_datasets'
                    script {
                        def forceFlag = params.FORCE_REGEN ? '--force-regen' : ''
                        bat "chcp 65001 > nul && .venv\\\\Scripts\\\\python.exe manage.py fill_ml_datasets --seed 42 ${forceFlag}"
                    }
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\check_dataset.py'
                }
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 5 · Drift Detection
        // Script : ci/run_drift.py
        // ────────────────────────────────────────────────────────────
        stage('5 - Drift Detection') {
            steps {
                bat 'IF NOT EXIST "%WORKSPACE%\\artifacts" mkdir "%WORKSPACE%\\artifacts"'
                dir("${BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\run_drift.py'
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
        // Script : ci/train_standard.py <STANDARD>
        // train_all_models() depuis ml/train_models.py
        // ────────────────────────────────────────────────────────────
        stage('6 - ML Training') {
            steps {
                dir("${BACKEND_DIR}") {
                    script {
                        def std = params.STANDARD
                        if (std == 'ALL' || std == 'ISO9001') {
                            bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\train_standard.py ISO9001'
                        }
                        if (std == 'ALL' || std == 'ISO27001') {
                            bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\train_standard.py ISO27001'
                        }
                        if (std == 'ALL' || std == 'TISAX') {
                            bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\train_standard.py TISAX'
                        }
                    }
                }
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 7 · Export Metriques
        // Script : ci/export_metrics.py
        // ────────────────────────────────────────────────────────────
        stage('7 - Export Metriques') {
            steps {
                bat 'IF NOT EXIST "%WORKSPACE%\\artifacts" mkdir "%WORKSPACE%\\artifacts"'
                dir("${BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\export_metrics.py'
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
        // Script : ci/update_training_job.py
        // ────────────────────────────────────────────────────────────
        stage('8 - TrainingJob Update') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\update_training_job.py'
                }
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 9 · Cleanup
        // ────────────────────────────────────────────────────────────
        stage('9 - Cleanup') {
            steps {
                bat '''
                    chcp 65001 > nul
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
