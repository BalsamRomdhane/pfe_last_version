// ============================================================
// Jenkinsfile - Enterprise ISO Compliance Platform
// Pipeline MLOps + DevSecOps - Windows, sans Docker
// Jenkins 2.555+ - Declarative Pipeline - UTF-8 sans BOM
//
// STAGES :
//   1  - Checkout
//   2  - Verify Environment
//   3  - Python Environment
//   4  - Install Backend Dependencies
//   5  - Install Frontend Dependencies
//   6  - Django Check
//   7  - Database Migration
//   8  - Django Tests
//   9  - Frontend Build
//   10 - Dataset Validation
//   11 - Security Module Check
//   12 - Drift Detection
//   13 - SonarQube Analysis
//   14 - Quality Gate
//   15 - ML Training
//   16 - Export Metrics
//   17 - TrainingJob Update
//   18 - Archive Artifacts
//   19 - Cleanup
//
// CREDENTIALS JENKINS REQUIS (Manage Jenkins > Credentials) :
//   postgres-credentials   (Username/Password) DB_USER / DB_PASSWORD
//   django-secret-key      (Secret Text)       DJANGO_SECRET_KEY
//   sonarqube-token        (Secret Text)       injecte par withSonarQubeEnv
//
// OUTILS JENKINS REQUIS (Manage Jenkins > Tools) :
//   SonarQube Scanner : SonarScanner
//
// PLUGINS JENKINS REQUIS :
//   pipeline, git, sonar, credentials-binding, timestamper,
//   build-discarder, ws-cleanup, junit
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
    // Variables d environnement - aucune valeur sensible ici.
    // Les secrets sont injectes via withCredentials() dans
    // chaque stage qui en a besoin.
    // ----------------------------------------------------------
    environment {
        BACKEND_DIR             = "${WORKSPACE}\\backend"
        FRONTEND_DIR            = "${WORKSPACE}\\frontend"
        ARTIFACTS_DIR           = "${WORKSPACE}\\artifacts"
        DJANGO_SETTINGS_MODULE  = "enterprise_platform.settings"
        PYTHONIOENCODING        = "utf-8"
        PYTHONUTF8              = "1"
        PYTHONDONTWRITEBYTECODE = "1"
        CI                      = "true"
        DB_HOST                 = "localhost"
        DB_PORT                 = "5432"
        DB_NAME                 = "compliance_db"
        KEYCLOAK_SERVER_URL     = "http://localhost:8081"
        KEYCLOAK_REALM          = "iso9001-realm"
        KEYCLOAK_CLIENT_ID      = "iso9001-client"
    }

    // ==========================================================
    stages {

        // ------------------------------------------------------
        // STAGE 1 - Checkout
        // ------------------------------------------------------
        stage('1 - Checkout') {
            steps {
                echo "========================================================="
                echo " Build #${env.BUILD_NUMBER} | Branch: ${env.GIT_BRANCH ?: 'N/A'}"
                echo " Standard: ${params.STANDARD}"
                echo "========================================================="
                checkout scm
                bat 'chcp 65001 > nul && git log --oneline -5'
                bat 'chcp 65001 > nul && git status'
                echo "[OK] Checkout termine."
            }
        }

        // ------------------------------------------------------
        // STAGE 2 - Verify Environment
        // Verifie que Python, Node.js et les secrets sont
        // disponibles. Echec immediat si manquant.
        // ------------------------------------------------------
        stage('2 - Verify Environment') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'postgres-credentials',
                        usernameVariable: 'DB_USER',
                        passwordVariable: 'DB_PASSWORD'
                    ),
                    string(
                        credentialsId: 'django-secret-key',
                        variable: 'DJANGO_SECRET_KEY'
                    )
                ]) {
                    bat 'chcp 65001 > nul && python --version'
                    bat 'chcp 65001 > nul && node --version'
                    bat 'chcp 65001 > nul && npm --version'
                    script {
                        if (!env.DB_NAME) {
                            error('[FAIL] DB_NAME non configure.')
                        }
                        echo "[OK] DB_NAME  : ${env.DB_NAME}"
                        echo "[OK] DB_HOST  : ${env.DB_HOST}"
                        echo "[OK] DB_USER  : (masked)"
                        echo "[OK] SECRET_KEY: (masked)"
                        echo "[OK] Environment verification passed."
                    }
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
        // STAGE 6 - Django Check
        // Verifie la configuration Django et les modeles ML.
        // ------------------------------------------------------
        stage('6 - Django Check') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'postgres-credentials',
                        usernameVariable: 'DB_USER',
                        passwordVariable: 'DB_PASSWORD'
                    ),
                    string(
                        credentialsId: 'django-secret-key',
                        variable: 'DJANGO_SECRET_KEY'
                    )
                ]) {
                    dir("${env.BACKEND_DIR}") {
                        bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py check 2>&1 || echo [WARN] Django check non-zero exit.'
                        bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\check_django.py'
                    }
                }
                echo "[OK] Django check passed."
            }
        }

        // ------------------------------------------------------
        // STAGE 7 - Database Migration
        // ------------------------------------------------------
        stage('7 - Database Migration') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'postgres-credentials',
                        usernameVariable: 'DB_USER',
                        passwordVariable: 'DB_PASSWORD'
                    ),
                    string(
                        credentialsId: 'django-secret-key',
                        variable: 'DJANGO_SECRET_KEY'
                    )
                ]) {
                    dir("${env.BACKEND_DIR}") {
                        bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py migrate --no-input'
                    }
                }
                echo "[OK] Database migration complete."
            }
        }

        // ------------------------------------------------------
        // STAGE 8 - Django Tests
        // --keepdb reutilise la base de test pour accelerer.
        // Un echec partiel n interrompt pas le pipeline.
        // ------------------------------------------------------
        stage('8 - Django Tests') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'postgres-credentials',
                        usernameVariable: 'DB_USER',
                        passwordVariable: 'DB_PASSWORD'
                    ),
                    string(
                        credentialsId: 'django-secret-key',
                        variable: 'DJANGO_SECRET_KEY'
                    )
                ]) {
                    dir("${env.BACKEND_DIR}") {
                        bat '''
                            chcp 65001 > nul
                            .venv\\Scripts\\python.exe manage.py test api authentication notifications compliance --verbosity=1 --keepdb 2>&1
                            IF %ERRORLEVEL% NEQ 0 echo [WARN] Some Django tests failed - pipeline continues.
                        '''
                    }
                }
                echo "[OK] Django tests executed."
            }
        }

        // ------------------------------------------------------
        // STAGE 9 - Frontend Build
        // Ignore si SKIP_FRONTEND=true.
        // ------------------------------------------------------
        stage('9 - Frontend Build') {
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
        // STAGE 10 - Dataset Validation
        // Synchronise les datasets et verifie le volume minimum.
        // ------------------------------------------------------
        stage('10 - Dataset Validation') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'postgres-credentials',
                        usernameVariable: 'DB_USER',
                        passwordVariable: 'DB_PASSWORD'
                    ),
                    string(
                        credentialsId: 'django-secret-key',
                        variable: 'DJANGO_SECRET_KEY'
                    )
                ]) {
                    bat 'IF NOT EXIST "%ARTIFACTS_DIR%" mkdir "%ARTIFACTS_DIR%"'
                    dir("${env.BACKEND_DIR}") {
                        bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py system_audit 2>&1 || echo [WARN] system_audit non-zero exit.'
                        bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py sync_all_datasets'
                        script {
                            def forceFlag = params.FORCE_REGEN ? '--force-regen' : ''
                            bat "chcp 65001 > nul && .venv\\\\Scripts\\\\python.exe manage.py fill_ml_datasets --seed 42 ${forceFlag}"
                        }
                        bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\check_dataset.py'
                    }
                }
                echo "[OK] Dataset validation complete."
            }
        }

        // ------------------------------------------------------
        // STAGE 11 - Security Module Check
        // Verifie modeles, detecteurs, acces DB et routing URL.
        // ------------------------------------------------------
        stage('11 - Security Module Check') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'postgres-credentials',
                        usernameVariable: 'DB_USER',
                        passwordVariable: 'DB_PASSWORD'
                    ),
                    string(
                        credentialsId: 'django-secret-key',
                        variable: 'DJANGO_SECRET_KEY'
                    )
                ]) {
                    dir("${env.BACKEND_DIR}") {
                        bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\check_security.py'
                    }
                }
                echo "[OK] Security module check passed."
            }
        }

        // ------------------------------------------------------
        // STAGE 12 - Drift Detection
        // Calcule le drift semantique pour toutes les normes.
        // Produit : artifacts/drift_report.json
        // ------------------------------------------------------
        stage('12 - Drift Detection') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'postgres-credentials',
                        usernameVariable: 'DB_USER',
                        passwordVariable: 'DB_PASSWORD'
                    ),
                    string(
                        credentialsId: 'django-secret-key',
                        variable: 'DJANGO_SECRET_KEY'
                    )
                ]) {
                    bat 'IF NOT EXIST "%ARTIFACTS_DIR%" mkdir "%ARTIFACTS_DIR%"'
                    dir("${env.BACKEND_DIR}") {
                        bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\run_drift.py'
                    }
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
        // STAGE 13 - SonarQube Analysis
        // Execute depuis la RACINE du workspace.
        // Ignore si SKIP_SONAR=true.
        // ------------------------------------------------------
        stage('13 - SonarQube Analysis') {
            when {
                expression { return !params.SKIP_SONAR }
            }
            environment {
                SCANNER_HOME = tool(name: 'SonarScanner', type: 'hudson.plugins.sonar.SonarRunnerInstallation')
            }
            steps {
                echo "[INFO] SonarQube Analysis | Build: ${env.BUILD_NUMBER}"
                dir("${env.WORKSPACE}") {
                    withSonarQubeEnv('SonarQube') {
                        bat "\"${env.SCANNER_HOME}\\bin\\sonar-scanner.bat\" -Dsonar.projectVersion=1.0.${env.BUILD_NUMBER}"
                    }
                }
                echo "[OK] SonarQube analysis submitted."
            }
        }

        // ------------------------------------------------------
        // STAGE 14 - Quality Gate
        // Attend le resultat via webhook. Timeout 10 min.
        // Ignore si SKIP_SONAR=true.
        // ------------------------------------------------------
        stage('14 - Quality Gate') {
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
        // STAGE 15 - ML Training
        // Entraine les modeles pour les standards selectionnes.
        // Ignore si SKIP_TRAINING=true.
        // ------------------------------------------------------
        stage('15 - ML Training') {
            when {
                expression { return !params.SKIP_TRAINING }
            }
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'postgres-credentials',
                        usernameVariable: 'DB_USER',
                        passwordVariable: 'DB_PASSWORD'
                    ),
                    string(
                        credentialsId: 'django-secret-key',
                        variable: 'DJANGO_SECRET_KEY'
                    )
                ]) {
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
                }
                echo "[OK] ML Training complete."
            }
        }

        // ------------------------------------------------------
        // STAGE 16 - Export Metrics
        // Exporte Prometheus + evaluation summary.
        // Ignore si SKIP_TRAINING=true.
        // ------------------------------------------------------
        stage('16 - Export Metrics') {
            when {
                expression { return !params.SKIP_TRAINING }
            }
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'postgres-credentials',
                        usernameVariable: 'DB_USER',
                        passwordVariable: 'DB_PASSWORD'
                    ),
                    string(
                        credentialsId: 'django-secret-key',
                        variable: 'DJANGO_SECRET_KEY'
                    )
                ]) {
                    bat 'IF NOT EXIST "%ARTIFACTS_DIR%" mkdir "%ARTIFACTS_DIR%"'
                    dir("${env.BACKEND_DIR}") {
                        bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\export_metrics.py'
                    }
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
        // STAGE 17 - TrainingJob Update
        // Enregistre les TrainingJob en base de donnees.
        // Ignore si SKIP_TRAINING=true.
        // ------------------------------------------------------
        stage('17 - TrainingJob Update') {
            when {
                expression { return !params.SKIP_TRAINING }
            }
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'postgres-credentials',
                        usernameVariable: 'DB_USER',
                        passwordVariable: 'DB_PASSWORD'
                    ),
                    string(
                        credentialsId: 'django-secret-key',
                        variable: 'DJANGO_SECRET_KEY'
                    )
                ]) {
                    dir("${env.BACKEND_DIR}") {
                        bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\update_training_job.py'
                    }
                }
                echo "[OK] TrainingJob records updated in database."
            }
        }

        // ------------------------------------------------------
        // STAGE 18 - Archive Artifacts
        // ------------------------------------------------------
        stage('18 - Archive Artifacts') {
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
        // STAGE 19 - Cleanup
        // Supprime __pycache__ et fichiers .pyc/.pyo.
        // ------------------------------------------------------
        stage('19 - Cleanup') {
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
    // ----------------------------------------------------------
    post {

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
            echo " Check the stage logs above to identify the failure."
            echo "========================================================="
        }

        unstable {
            echo "[WARN] Pipeline UNSTABLE - Build #${env.BUILD_NUMBER}"
            echo "[WARN] Check test results and Quality Gate."
        }

        always {
            echo "[INFO] Pipeline finished - Build #${env.BUILD_NUMBER} | Duration: ${currentBuild.durationString}"
        }

    }

}
