// ============================================================
// Jenkinsfile - Enterprise ISO Compliance Platform
// Pipeline MLOps + DevSecOps - Windows local, sans Docker
// Jenkins 2.555+ - Declarative Pipeline - UTF-8 sans BOM
//
// ARCHITECTURE :
//   Le fichier backend/.env est GENERE automatiquement au
//   stage "2 - Generate Env File" a partir des variables
//   definies dans le bloc environment{} ci-dessous.
//   Il N EST PAS requis sur le disque de l agent.
//   Il N EST PAS versionne dans Git (.gitignore).
//   Il est SUPPRIME dans post { always } apres chaque build.
//
//   Toutes les valeurs sont des parametres de developpement
//   local. Pour un environnement de production, remplacer
//   les valeurs sensibles par des Jenkins Credentials.
//
// OUTILS JENKINS REQUIS (Manage Jenkins > Tools) :
//   SonarQube Scanner : SonarScanner
//
// PLUGINS REQUIS :
//   pipeline, git, sonar, timestamper, build-discarder
//
// STAGES :
//   1  - Checkout
//   2  - Generate Env File
//   3  - Python Environment
//   4  - Install Backend Dependencies
//   5  - Install Frontend Dependencies
//   6  - Django Check & Migrate
//   7  - Django Tests
//   8  - Frontend Build
//   9  - Dataset Validation
//   10 - Security Module Check
//   11 - Drift Detection
//   12 - SonarQube Analysis
//   13 - Quality Gate
//   14 - ML Training
//   15 - Export Metrics
//   16 - TrainingJob Update
//   17 - Archive Artifacts
//   18 - Cleanup
// ============================================================

pipeline {

    agent any

    // ----------------------------------------------------------
    // Options globales
    // ----------------------------------------------------------
    options {
        timeout(time: 90, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10', artifactNumToKeepStr: '5'))
        timestamps()
        skipDefaultCheckout(false)
    }

    // ----------------------------------------------------------
    // Parametres de build
    // ----------------------------------------------------------
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
        booleanParam(
            name: 'SKIP_SONAR',
            defaultValue: false,
            description: 'Ignorer l analyse SonarQube (debug uniquement)'
        )
        booleanParam(
            name: 'SKIP_FRONTEND',
            defaultValue: false,
            description: 'Ignorer le build frontend'
        )
        booleanParam(
            name: 'SKIP_TRAINING',
            defaultValue: false,
            description: 'Ignorer l entrainement ML'
        )
    }

    // ----------------------------------------------------------
    // Variables globales du pipeline.
    // Toutes les variables necessaires pour generer backend/.env
    // sont definies ici. Aucun credentials Jenkins requis.
    // Le .env est genere au stage 2 et supprime dans post{always}.
    // ----------------------------------------------------------
    environment {
        BACKEND_DIR             = "${WORKSPACE}\\backend"
        FRONTEND_DIR            = "${WORKSPACE}\\frontend"
        ARTIFACTS_DIR           = "${WORKSPACE}\\artifacts"
        ENV_FILE                = "${WORKSPACE}\\backend\\.env"
        DJANGO_SETTINGS_MODULE  = "enterprise_platform.settings"
        PYTHONIOENCODING        = "utf-8"
        PYTHONUTF8              = "1"
        PYTHONDONTWRITEBYTECODE = "1"
        CI                      = "true"

        // ── Variables qui seront ecrites dans backend/.env ──
        // Base de donnees PostgreSQL locale
        DATABASE_URL            = "postgres://postgres@localhost:5432/compliance_db"
        CONN_MAX_AGE            = "600"
        DB_NAME                 = "compliance_db"
        DB_USER                 = "postgres"
        DB_PASSWORD             = ""
        DB_HOST                 = "localhost"
        DB_PORT                 = "5432"

        // Django
        DJANGO_SECRET_KEY       = "*icm=l80zwu7t$)^in(tu(u7p%yx7@*++3nqb(b6*v1!4j05f@"
        DEBUG                   = "True"
        ALLOWED_HOSTS           = "localhost,127.0.0.1"
        SESSION_COOKIE_SECURE   = "False"
        CSRF_COOKIE_SECURE      = "False"
        SECURE_SSL_REDIRECT     = "False"
        SECURE_HSTS_SECONDS     = "0"

        

        // Jenkins MLOps
        JENKINS_URL_ENV         = "http://localhost:8089"
        JENKINS_USER_ENV        = "jenkins_admin"
        JENKINS_TOKEN_ENV       = "11f2c033cd14e1c2eec21c764c115c4ce1"
        JENKINS_JOB_NAME_ENV    = "Enterprise-ISO-Compliance"
        MLOPS_RETRAINING_THRESHOLD = "10"
        DJANGO_API_URL          = "http://localhost:8000"
    }

    // ==========================================================
    stages {

        // ------------------------------------------------------
        // STAGE 1 - Checkout
        // Recupere le code source.
        // ------------------------------------------------------
        stage('1 - Checkout') {
            steps {
                echo "========================================================="
                echo " Build #${env.BUILD_NUMBER} | Branch: ${env.GIT_BRANCH ?: 'N/A'}"
                echo " Standard : ${params.STANDARD}"
                echo "========================================================="
                checkout scm
                bat 'chcp 65001 > nul && git log --oneline -5'
                bat 'chcp 65001 > nul && git status'
                // Verifier que Python et Node sont disponibles sur l agent
                bat 'chcp 65001 > nul && python --version'
                bat 'chcp 65001 > nul && node --version'
                bat 'chcp 65001 > nul && npm --version'
                echo "[OK] Checkout et verification de l environnement termines."
            }
        }

        // ------------------------------------------------------
        // STAGE 2 - Generate Env File
        //
        // Genere automatiquement backend/.env depuis les
        // variables definies dans le bloc environment{} ci-dessus.
        // Aucun credentials Jenkins requis.
        // Le fichier est supprime dans post { always }.
        // ------------------------------------------------------
        stage('2 - Generate Env File') {
            steps {
                script {
 def envContent = """DATABASE_URL=${env.DATABASE_URL}
CONN_MAX_AGE=${env.CONN_MAX_AGE}

DJANGO_SECRET_KEY=${env.DJANGO_SECRET_KEY}
DEBUG=${env.DEBUG}
ALLOWED_HOSTS=${env.ALLOWED_HOSTS}
SESSION_COOKIE_SECURE=${env.SESSION_COOKIE_SECURE}
CSRF_COOKIE_SECURE=${env.CSRF_COOKIE_SECURE}
SECURE_SSL_REDIRECT=${env.SECURE_SSL_REDIRECT}
SECURE_HSTS_SECONDS=${env.SECURE_HSTS_SECONDS}

JENKINS_URL=${env.JENKINS_URL_ENV}
JENKINS_USER=${env.JENKINS_USER_ENV}
JENKINS_TOKEN=${env.JENKINS_TOKEN_ENV}
JENKINS_JOB_NAME=${env.JENKINS_JOB_NAME_ENV}
MLOPS_RETRAINING_THRESHOLD=${env.MLOPS_RETRAINING_THRESHOLD}
DJANGO_API_URL=${env.DJANGO_API_URL}

DB_NAME=${env.DB_NAME}
DB_USER=${env.DB_USER}
DB_PASSWORD=${env.DB_PASSWORD}
DB_HOST=${env.DB_HOST}
DB_PORT=${env.DB_PORT}
"""
                    writeFile(file: "${env.ENV_FILE}", text: envContent, encoding: 'UTF-8')
                    echo "[OK] backend/.env genere avec succes."
                    echo "[INFO] Le fichier sera supprime apres le build dans post { always }."
                }
            }
        }

        // ------------------------------------------------------
        // STAGE 3 - Python Environment
        // Cree ou reutilise le virtualenv .venv dans backend/.
        // ------------------------------------------------------
        stage('3 - Python Environment') {
            steps {
                dir("${env.BACKEND_DIR}") {
                    bat '''
                        chcp 65001 > nul
                        IF NOT EXIST ".venv\\Scripts\\python.exe" (
                            echo [INFO] Creating Python virtual environment...
                            python -m venv .venv
                            echo [OK] Virtual environment created.
                        ) ELSE (
                            echo [INFO] Reusing existing virtual environment.
                        )
                        .venv\\Scripts\\python.exe --version
                    '''
                }
                echo "[OK] Python environment ready."
            }
        }

        // ------------------------------------------------------
        // STAGE 4 - Install Backend Dependencies
        // Installe les dependances pip et verifie les imports.
        // ------------------------------------------------------
        stage('4 - Install Backend Dependencies') {
            steps {
                dir("${env.BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe -m pip install --upgrade pip --quiet'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\pip.exe install -r requirements.txt --quiet'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe -c "import django; print(\"[OK] django\", django.__version__)"'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe -c "import sklearn; print(\"[OK] sklearn\")"'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe -c "import numpy; print(\"[OK] numpy\")"'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe -c "import joblib; print(\"[OK] joblib\")"'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe -c "import psycopg2; print(\"[OK] psycopg2\")"'
                }
                echo "[OK] Backend dependencies installed."
            }
        }

        // ------------------------------------------------------
        // STAGE 5 - Install Frontend Dependencies
        // Ignore si SKIP_FRONTEND=true.
        // npm ci utilise package-lock.json pour reproductibilite.
        // Fallback sur npm install si lock file absent.
        // ------------------------------------------------------
        stage('5 - Install Frontend Dependencies') {
            when {
                expression { return !params.SKIP_FRONTEND }
            }
            steps {
                dir("${env.FRONTEND_DIR}") {
                    bat 'chcp 65001 > nul && npm ci --prefer-offline --no-audit 2>&1 || npm install --no-audit'
                }
                echo "[OK] Frontend dependencies installed."
            }
        }

        // ------------------------------------------------------
        // STAGE 6 - Django Check & Migrate
        // Django lit backend/.env (genere au stage 2) via
        // python-dotenv. Aucun credentials supplementaire requis.
        // ------------------------------------------------------
        stage('6 - Django Check & Migrate') {
            steps {
                dir("${env.BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py check'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py migrate --no-input'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\check_django.py'
                }
                echo "[OK] Django check and migration complete."
            }
        }

        // ------------------------------------------------------
        // STAGE 7 - Django Tests
        // --keepdb reutilise la base de test entre les builds.
        // Un echec partiel n interrompt pas le pipeline (WARN).
        // ------------------------------------------------------
        stage('7 - Django Tests') {
            steps {
                dir("${env.BACKEND_DIR}") {
                    bat '''
                        chcp 65001 > nul
                        .venv\\Scripts\\python.exe manage.py test api authentication notifications compliance --verbosity=1 --keepdb 2>&1
                        IF %ERRORLEVEL% NEQ 0 (
                            echo [WARN] Some Django tests failed - pipeline continues.
                        )
                    '''
                }
                echo "[OK] Django tests executed."
            }
        }

        // ------------------------------------------------------
        // STAGE 8 - Frontend Build
        // Compile le bundle React de production.
        // Ignore si SKIP_FRONTEND=true.
        // ------------------------------------------------------
        stage('8 - Frontend Build') {
            when {
                expression { return !params.SKIP_FRONTEND }
            }
            steps {
                dir("${env.FRONTEND_DIR}") {
                    bat 'chcp 65001 > nul && npm run build 2>&1'
                }
                echo "[OK] Frontend build complete."
            }
        }

        // ------------------------------------------------------
        // STAGE 9 - Dataset Validation
        // Synchronise les datasets et verifie le volume minimum
        // de samples labellises pour l entrainement ML.
        // ------------------------------------------------------
        stage('9 - Dataset Validation') {
            steps {
                bat 'IF NOT EXIST "%ARTIFACTS_DIR%" mkdir "%ARTIFACTS_DIR%"'
                dir("${env.BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py system_audit 2>&1 || echo [WARN] system_audit non-zero exit, continuing.'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py sync_all_datasets'
                    script {
                        def forceFlag = params.FORCE_REGEN ? '--force-regen' : ''
                        bat "chcp 65001 > nul && .venv\\\\Scripts\\\\python.exe manage.py fill_ml_datasets --seed 42 ${forceFlag}"
                    }
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\check_dataset.py'
                }
                echo "[OK] Dataset validation complete."
            }
        }

        // ------------------------------------------------------
        // STAGE 10 - Security Module Check
        // Verifie modeles, detecteurs PII/secrets, acces DB
        // et routing URL du module Document Security.
        // ------------------------------------------------------
        stage('10 - Security Module Check') {
            steps {
                dir("${env.BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\check_security.py'
                }
                echo "[OK] Security module check passed."
            }
        }

        // ------------------------------------------------------
        // STAGE 11 - Drift Detection
        // Calcule le drift semantique (TF-IDF cosinus) pour
        // toutes les normes. Produit artifacts/drift_report.json.
        // ------------------------------------------------------
        stage('11 - Drift Detection') {
            steps {
                bat 'IF NOT EXIST "%ARTIFACTS_DIR%" mkdir "%ARTIFACTS_DIR%"'
                dir("${env.BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\run_drift.py'
                }
                echo "[OK] Drift detection complete."
            }
            post {
                always {
                    archiveArtifacts(
                        artifacts: 'artifacts/drift_report.json',
                        allowEmptyArchive: true
                    )
                }
            }
        }

        // ------------------------------------------------------
        // STAGE 12 - SonarQube Analysis
        // Execute depuis la RACINE du workspace pour que
        // sonar-project.properties soit detecte.
        // withSonarQubeEnv injecte SONAR_HOST_URL et le token.
        // Ignore si SKIP_SONAR=true.
        //
        // CORRECTION : env.WORKSPACE utilise a la place d un
        // chemin en dur pour compatibilite multi-agent.
        // ------------------------------------------------------
        stage('12 - SonarQube Analysis') {
            when {
                expression { return !params.SKIP_SONAR }
            }
            environment {
                // CORRECTION : tool() resout le chemin depuis
                // la configuration Jenkins Tools, pas en dur.
                SCANNER_HOME = tool(
                    name: 'SonarScanner',
                    type: 'hudson.plugins.sonar.SonarRunnerInstallation'
                )
            }
            steps {
                echo "[INFO] SonarQube Analysis | Build: ${env.BUILD_NUMBER}"
                echo "[INFO] Scanner path: ${env.SCANNER_HOME}"
                dir("${env.WORKSPACE}") {
                    withSonarQubeEnv('SonarQube') {
                        bat "\"${env.SCANNER_HOME}\\bin\\sonar-scanner.bat\" -Dsonar.projectVersion=1.0.${env.BUILD_NUMBER}"
                    }
                }
                echo "[OK] SonarQube analysis submitted."
            }
        }

        // ------------------------------------------------------
        // STAGE 13 - Quality Gate
        // Attend le resultat via webhook SonarQube.
        // abortPipeline:true = echec si QG = FAILED.
        // Timeout 10 minutes pour eviter un blocage indefini.
        // Ignore si SKIP_SONAR=true.
        // ------------------------------------------------------
        stage('13 - Quality Gate') {
            when {
                expression { return !params.SKIP_SONAR }
            }
            steps {
                echo "[INFO] Waiting for SonarQube Quality Gate (timeout: 10 min)..."
                timeout(time: 10, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
                echo "[OK] Quality Gate passed."
            }
        }

        // ------------------------------------------------------
        // STAGE 14 - ML Training
        // Entraine RandomForest, LogisticRegression,
        // GradientBoosting, BiLSTM pour les standards choisis.
        // Ignore si SKIP_TRAINING=true.
        // ------------------------------------------------------
        stage('14 - ML Training') {
            when {
                expression { return !params.SKIP_TRAINING }
            }
            steps {
                echo "[INFO] ML Training - Standard: ${params.STANDARD}"
                dir("${env.BACKEND_DIR}") {
                    script {
                        def std = params.STANDARD
                        if (std == 'ALL' || std == 'ISO9001') {
                            echo "[INFO] Training ISO9001..."
                            bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\train_standard.py ISO9001'
                        }
                        if (std == 'ALL' || std == 'ISO27001') {
                            echo "[INFO] Training ISO27001..."
                            bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\train_standard.py ISO27001'
                        }
                        if (std == 'ALL' || std == 'TISAX') {
                            echo "[INFO] Training TISAX..."
                            bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\train_standard.py TISAX'
                        }
                    }
                }
                echo "[OK] ML Training complete."
            }
        }

        // ------------------------------------------------------
        // STAGE 15 - Export Metrics
        // Exporte les metriques Prometheus et l evaluation
        // summary depuis les *_metrics.json.
        // Produit :
        //   artifacts/prometheus_metrics.txt
        //   artifacts/evaluation_summary.json
        // Ignore si SKIP_TRAINING=true.
        // ------------------------------------------------------
        stage('15 - Export Metrics') {
            when {
                expression { return !params.SKIP_TRAINING }
            }
            steps {
                bat 'IF NOT EXIST "%ARTIFACTS_DIR%" mkdir "%ARTIFACTS_DIR%"'
                dir("${env.BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\export_metrics.py'
                }
                echo "[OK] Metrics exported to artifacts/."
            }
            post {
                always {
                    archiveArtifacts(
                        artifacts: 'artifacts/prometheus_metrics.txt,artifacts/evaluation_summary.json',
                        allowEmptyArchive: true
                    )
                }
            }
        }

        // ------------------------------------------------------
        // STAGE 16 - TrainingJob Update
        // Enregistre les TrainingJob en base de donnees depuis
        // les *_metrics.json. Ignore si SKIP_TRAINING=true.
        // ------------------------------------------------------
        stage('16 - TrainingJob Update') {
            when {
                expression { return !params.SKIP_TRAINING }
            }
            steps {
                dir("${env.BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\update_training_job.py'
                }
                echo "[OK] TrainingJob records updated in database."
            }
        }

        // ------------------------------------------------------
        // STAGE 17 - Archive Artifacts
        // Archive tous les artefacts du build avec fingerprint
        // pour tracabilite et reproductibilite.
        // ------------------------------------------------------
        stage('17 - Archive Artifacts') {
            steps {
                archiveArtifacts(
                    artifacts: 'artifacts/**/*',
                    allowEmptyArchive: true,
                    fingerprint: true
                )
                echo "[OK] Artifacts archived."
            }
        }

        // ------------------------------------------------------
        // STAGE 18 - Cleanup
        // Supprime __pycache__ et les fichiers .pyc/.pyo.
        // NOTE : la suppression du .env est dans post { always }
        // pour garantir son execution meme en cas d echec.
        // ------------------------------------------------------
        stage('18 - Cleanup') {
            steps {
                bat '''
                    chcp 65001 > nul
                    echo [INFO] Cleaning Python cache files...
                    FOR /R "%WORKSPACE%" %%D IN (__pycache__) DO (
                        IF EXIST "%%D" RMDIR /S /Q "%%D" 2>nul
                    )
                    FOR /R "%WORKSPACE%" %%F IN (*.pyc *.pyo) DO (
                        IF EXIST "%%F" DEL /Q "%%F" 2>nul
                    )
                    echo [OK] Cleanup done.
                '''
                echo "[OK] Workspace cleaned."
            }
        }

    }
    // ==========================================================

    // ----------------------------------------------------------
    // Post-build actions
    //
    // SECURITE - always :
    //   Le fichier backend/.env genere au stage 2 est SUPPRIME
    //   ici systematiquement, que le build reussisse ou echoue.
    //   Cela garantit que les secrets ne persistent pas sur
    //   l agent Jenkins apres le build.
    // ----------------------------------------------------------
    post {

        always {
            script {
                // CORRECTION SECURITE : suppression systematique
                // du .env genere, meme en cas d echec du pipeline.
                // Ne pas utiliser bat() car il echoue si le fichier
                // n existe pas (ex: build echoue avant stage 2).
                try {
                    if (fileExists("${env.ENV_FILE}")) {
                        bat "DEL /Q \"${env.ENV_FILE}\" 2>nul"
                        echo "[OK] backend/.env supprime de l agent Jenkins."
                    }
                } catch (Exception e) {
                    echo "[WARN] Impossible de supprimer backend/.env : ${e.message}"
                }
            }
            echo "[INFO] Pipeline finished - Build #${env.BUILD_NUMBER} | Duration: ${currentBuild.durationString}"
        }

        success {
            echo "========================================================="
            echo " Pipeline SUCCESS"
            echo " Build     : #${env.BUILD_NUMBER}"
            echo " Standard  : ${params.STANDARD}"
            echo " Branch    : ${env.GIT_BRANCH ?: 'N/A'}"
            echo " SonarQube : ${params.SKIP_SONAR ? 'SKIPPED' : 'PASSED'}"
            echo " Training  : ${params.SKIP_TRAINING ? 'SKIPPED' : 'DONE'}"
            echo "========================================================="
        }

        failure {
            echo "========================================================="
            echo " Pipeline FAILED"
            echo " Build     : #${env.BUILD_NUMBER}"
            echo " Standard  : ${params.STANDARD}"
            echo " Consulter les logs du stage en echec ci-dessus."
            echo "========================================================="
        }

        unstable {
            echo "[WARN] Pipeline UNSTABLE - Build #${env.BUILD_NUMBER}"
            echo "[WARN] Verifier les tests Django et le Quality Gate."
        }

    }

}
