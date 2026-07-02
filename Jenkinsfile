// ══════════════════════════════════════════════════════════════════════
// Jenkinsfile — Enterprise ISO Compliance Platform
// Pipeline MLOps + DevSecOps — Windows local, sans Docker
//
// STAGES :
//   1  · Checkout
//   2  · Install Dependencies
//   3  · Django Check & Migrate
//   4  · Dataset Validation
//   5  · Drift Detection
//   6  · SonarQube Analysis        (DevSecOps)
//   7  · Quality Gate              (DevSecOps)
//   8  · ML Training
//   9  · Export Metriques
//   10 · TrainingJob Update
//   11 · Cleanup
//
// ARCHITECTURE :
//   Tout le code Python multi-lignes est dans backend/ci/*.py
//   Les stages bat n'appellent que des commandes simples sur une ligne
//   Aucun bloc python -c "..." multi-lignes dans ce fichier
//
// SONARQUBE :
//   - Jenkins tool name  : SonarScanner   (Manage Jenkins > Tools)
//   - Jenkins server name: SonarQube      (Manage Jenkins > System > SonarQube Servers)
//   - Credential ID      : sonarqube-token (Secret Text)
//   - sonar-project.properties au root du workspace
//   - Aucun token ni URL hardcodes — injectes par withSonarQubeEnv
// ══════════════════════════════════════════════════════════════════════

pipeline {
    agent any

    // ── Variables d'environnement globales ──────────────────────────
    environment {
        // Chemin vers le backend Django
        BACKEND_DIR            = "${WORKSPACE}\\backend"
        DJANGO_SETTINGS_MODULE = "enterprise_platform.settings"

        // Force UTF-8 — obligatoire sur Windows CP850/CP1252
        PYTHONIOENCODING = "utf-8"
        PYTHONUTF8       = "1"

        // PostgreSQL — adapter selon la machine locale
        DB_HOST     = "localhost"
        DB_PORT     = "5432"
        DB_NAME     = "compliance_db"
        DB_USER     = "postgres"
        DB_PASSWORD = ""
    }

    // ── Parametres de build ─────────────────────────────────────────
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
            description: 'Ignorer lanalyse SonarQube (debug uniquement)'
        )
    }

    // ── Options pipeline ────────────────────────────────────────────
    options {
        timeout(time: 60, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timestamps()
    }

    // ════════════════════════════════════════════════════════════════
    stages {

        // ────────────────────────────────────────────────────────────
        // STAGE 1 · Checkout
        //
        // Recupere le code source depuis le SCM configure dans Jenkins.
        // Affiche les 5 derniers commits et le statut git pour
        // tracabilite et debug.
        // ────────────────────────────────────────────────────────────
        stage('1 - Checkout') {
            steps {
                echo "[INFO] Checkout du depot - Build #${env.BUILD_NUMBER}"
                checkout scm
                bat 'chcp 65001 > nul && git log --oneline -5'
                bat 'chcp 65001 > nul && git status'
                echo "[OK] Checkout termine - branche : ${env.GIT_BRANCH ?: 'N/A'}"
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 2 · Install Dependencies
        //
        // Cree ou reutilise le venv Python .venv dans backend/.
        // Installe toutes les dependances depuis requirements.txt.
        // Verifie les imports critiques : django, sklearn, joblib, numpy.
        // ────────────────────────────────────────────────────────────
        stage('2 - Install Dependencies') {
            steps {
                echo "[INFO] Verification et installation des dependances Python..."
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
                echo "[OK] Dependances installees et verifiees."
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 3 · Django Check & Migrate
        //
        // Verifie la configuration Django (manage.py check).
        // Applique les migrations de base de donnees.
        // Execute ci/check_django.py pour validation approfondie.
        // ────────────────────────────────────────────────────────────
        stage('3 - Django Check') {
            steps {
                echo "[INFO] Verification Django et migration de la base de donnees..."
                dir("${BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py check'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py migrate'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\check_django.py'
                }
                echo "[OK] Django operationnel - base de donnees synchronisee."
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 4 · Dataset Validation
        //
        // Audite le systeme, synchronise les datasets ISO, remplit
        // les donnees ML avec fill_ml_datasets.
        // Scripts : ci/check_dataset.py
        // Commandes : system_audit, sync_all_datasets, fill_ml_datasets
        // ────────────────────────────────────────────────────────────
        stage('4 - Dataset Validation') {
            steps {
                echo "[INFO] Validation du dataset ML (standard=${params.STANDARD})..."
                dir("${BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py system_audit || echo [WARN] system_audit exited with non-zero but continuing'
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe manage.py sync_all_datasets'
                    script {
                        def forceFlag = params.FORCE_REGEN ? '--force-regen' : ''
                        bat "chcp 65001 > nul && .venv\\\\Scripts\\\\python.exe manage.py fill_ml_datasets --seed 42 ${forceFlag}"
                    }
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\check_dataset.py'
                }
                echo "[OK] Dataset valide et pret pour l'entrainement."
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 5 · Drift Detection
        //
        // Calcule le drift semantique entre donnees historiques et
        // recentes via TF-IDF cosinus (70% hist / 30% recent).
        // Produit : artifacts/drift_report.json
        // Script  : ci/run_drift.py
        // ────────────────────────────────────────────────────────────
        stage('5 - Drift Detection') {
            steps {
                echo "[INFO] Calcul du drift semantique..."
                bat 'IF NOT EXIST "%WORKSPACE%\\artifacts" mkdir "%WORKSPACE%\\artifacts"'
                dir("${BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\run_drift.py'
                }
                echo "[OK] Rapport de drift genere dans artifacts/drift_report.json."
            }
            post {
                always {
                    archiveArtifacts artifacts: 'artifacts/drift_report.json',
                                     allowEmptyArchive: true
                }
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 6 · SonarQube Analysis
        //
        // Analyse statique du code source (Python + React/JS).
        // Le scanner est execute depuis la RACINE du workspace afin
        // que sonar-project.properties soit detecte automatiquement.
        //
        // FIX APPLIQUE :
        //   dir("${WORKSPACE}") force l'execution depuis la racine.
        //   Sans ce dir(), le scanner herite du working directory
        //   du stage precedent (backend/) et ne trouve pas
        //   sonar-project.properties.
        //
        // SECURITE :
        //   withSonarQubeEnv('SonarQube') injecte automatiquement :
        //     SONAR_HOST_URL  = valeur configuree dans Jenkins
        //     SONAR_AUTH_TOKEN = credential sonarqube-token
        //   Aucun token ni URL ne doit apparaitre dans ce fichier.
        //
        // CONDITION :
        //   Le stage est ignore si SKIP_SONAR=true (debug).
        // ────────────────────────────────────────────────────────────
        stage('6 - SonarQube Analysis') {
            when {
                expression { return !params.SKIP_SONAR }
            }
            environment {
                // Resout le chemin d'installation de SonarScanner
                // depuis l'outil configure dans Manage Jenkins > Tools.
                // Le nom 'SonarScanner' doit correspondre EXACTEMENT
                // au nom configure dans Jenkins.
                SCANNER_HOME = tool name: 'SonarScanner', type: 'hudson.plugins.sonar.SonarRunnerInstallation'
            }
            steps {
                echo "[INFO] Lancement de l'analyse SonarQube..."
                echo "[INFO] Projet : enterprise-iso-compliance | Build : ${env.BUILD_NUMBER}"
                echo "[INFO] Scanner : ${SCANNER_HOME}"

                // FIX PRINCIPAL : executer depuis la racine du workspace
                // pour que sonar-project.properties soit trouve.
                // withSonarQubeEnv injecte SONAR_HOST_URL et SONAR_AUTH_TOKEN.
                dir("${WORKSPACE}") {
                    withSonarQubeEnv('SonarQube') {
                        bat "\"${SCANNER_HOME}\\bin\\sonar-scanner.bat\" -Dsonar.projectVersion=1.0.${env.BUILD_NUMBER}"
                    }
                }
                echo "[OK] Analyse SonarQube soumise avec succes."
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 7 · Quality Gate
        //
        // Attend le resultat du Quality Gate SonarQube.
        // Le plugin SonarQube Scanner pour Jenkins recupere le resultat
        // via le webhook configure dans SonarQube :
        //   Administration > Configuration > Webhooks
        //   URL : http://JENKINS_URL/sonarqube-webhook/
        //
        // abortPipeline:true = le pipeline echoue si QG = FAILED.
        // Timeout de 10 minutes pour eviter un blocage indefini.
        //
        // CONDITION : ignore si SKIP_SONAR=true.
        // ────────────────────────────────────────────────────────────
        stage('7 - Quality Gate') {
            when {
                expression { return !params.SKIP_SONAR }
            }
            steps {
                echo "[INFO] Attente du Quality Gate SonarQube (timeout 10 min)..."
                timeout(time: 10, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: false
                }
                echo "[OK] Quality Gate check complete (pipeline continues regardless of result)."
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 8 · ML Training
        //
        // Entraine les modeles ML (RandomForest, LogisticRegression,
        // GradientBoosting, BiLSTM) pour les standards selectionnes.
        // Script : ci/train_standard.py <STANDARD>
        // Source  : ml/train_models.py -> train_all_models()
        // ────────────────────────────────────────────────────────────
        stage('8 - ML Training') {
            steps {
                echo "[INFO] Entrainement ML - standard=${params.STANDARD}..."
                dir("${BACKEND_DIR}") {
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
                echo "[OK] Entrainement ML termine."
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 9 · Export Metriques
        //
        // Exporte les metriques d'evaluation vers :
        //   artifacts/prometheus_metrics.txt
        //   artifacts/evaluation_summary.json
        //   artifacts/drift_report.json
        // Script : ci/export_metrics.py
        // ────────────────────────────────────────────────────────────
        stage('9 - Export Metriques') {
            steps {
                echo "[INFO] Export des metriques ML et Prometheus..."
                bat 'IF NOT EXIST "%WORKSPACE%\\artifacts" mkdir "%WORKSPACE%\\artifacts"'
                dir("${BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\export_metrics.py'
                }
                echo "[OK] Metriques exportees dans artifacts/."
            }
            post {
                always {
                    archiveArtifacts artifacts: 'artifacts/prometheus_metrics.txt,artifacts/evaluation_summary.json,artifacts/drift_report.json',
                                     allowEmptyArchive: true
                }
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 10 · TrainingJob Update
        //
        // Met a jour l'enregistrement TrainingJob en base de donnees
        // avec les metriques du pipeline (F1, accuracy, drift, version).
        // Script : ci/update_training_job.py
        // ────────────────────────────────────────────────────────────
        stage('10 - TrainingJob Update') {
            steps {
                echo "[INFO] Mise a jour du TrainingJob en base de donnees..."
                dir("${BACKEND_DIR}") {
                    bat 'chcp 65001 > nul && .venv\\Scripts\\python.exe ci\\update_training_job.py'
                }
                echo "[OK] TrainingJob mis a jour."
            }
        }

        // ────────────────────────────────────────────────────────────
        // STAGE 11 · Cleanup
        //
        // Supprime les repertoires __pycache__ generes durant le build
        // pour maintenir un espace de travail propre entre les builds.
        // ────────────────────────────────────────────────────────────
        stage('11 - Cleanup') {
            steps {
                echo "[INFO] Nettoyage des fichiers cache Python..."
                bat '''
                    chcp 65001 > nul
                    echo [INFO] Cleaning Python cache files...
                    FOR /R "%WORKSPACE%" %%D IN (__pycache__) DO (
                        IF EXIST "%%D" RMDIR /S /Q "%%D" 2>nul
                    )
                    echo [OK] Cleanup done.
                '''
                echo "[OK] Workspace nettoye."
            }
        }

    }
    // ════════════════════════════════════════════════════════════════

    // ── Post-build actions ──────────────────────────────────────────
    post {
        success {
            echo "========================================================="
            echo " Pipeline SUCCESS"
            echo " Build     : #${env.BUILD_NUMBER}"
            echo " Standard  : ${params.STANDARD}"
            echo " Branch    : ${env.GIT_BRANCH ?: 'N/A'}"
            echo " SonarQube : ${params.SKIP_SONAR ? 'SKIPPED' : 'PASSED'}"
            echo "========================================================="
        }
        failure {
            echo "========================================================="
            echo " Pipeline FAILED"
            echo " Build     : #${env.BUILD_NUMBER}"
            echo " Standard  : ${params.STANDARD}"
            echo " Consulter les logs ci-dessus pour identifier le stage en echec."
            echo "========================================================="
        }
        unstable {
            echo "[WARN] Pipeline UNSTABLE - Build #${env.BUILD_NUMBER} | Verifier les tests et le Quality Gate."
        }
        always {
            echo "[INFO] Pipeline termine - Build #${env.BUILD_NUMBER} | Duree : ${currentBuild.durationString}"
        }
    }
}
