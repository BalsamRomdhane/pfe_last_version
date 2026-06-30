//
=========================================================================
// Jenkinsfile (structure reconstruite) // IMPORTANT : adapte les
commandes ci-dessous à ton projet si nécessaire. //
=========================================================================

pipeline { agent any

    environment {
        BACKEND_DIR = "${WORKSPACE}\\backend"
        DJANGO_SETTINGS_MODULE = "enterprise_platform.settings"
        PYTHONIOENCODING = "utf-8"
        PYTHONUTF8 = "1"
    }

    options {
        timeout(time: 60, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timestamps()
    }

    parameters {
        choice(name: 'STANDARD', choices: ['ALL','ISO9001','ISO27001','TISAX'],
               description: 'Norme à entraîner')
        booleanParam(name: 'FORCE_REGEN', defaultValue: false,
                     description: 'Forcer la régénération')
        booleanParam(name: 'SKIP_SONAR', defaultValue: false,
                     description: 'Ignorer SonarQube')
    }

    stages {

        stage('1 - Checkout') {
            steps {
                checkout scm
            }
        }

        stage('2 - Install Dependencies') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat '.venv\\Scripts\\python.exe -m pip install -r requirements.txt'
                }
            }
        }

        stage('3 - Django Check') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat '.venv\\Scripts\\python.exe manage.py check'
                    bat '.venv\\Scripts\\python.exe manage.py migrate'
                }
            }
        }

        stage('3.5 - Django Tests') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat '.venv\\Scripts\\python.exe manage.py test'
                }
            }
        }

        stage('4 - Dataset Validation') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat '.venv\\Scripts\\python.exe manage.py sync_all_datasets'
                }
            }
        }

        stage('4.5 - Security Analysis') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat '.venv\\Scripts\\python.exe ci\\check_security.py'
                }
            }
        }

        stage('5 - Drift Detection') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat '.venv\\Scripts\\python.exe ci\\run_drift.py'
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'artifacts/drift_report.json', allowEmptyArchive: true
                }
            }
        }

        stage('6 - SonarQube Analysis') {
            when {
                expression { !params.SKIP_SONAR }
            }
            environment {
                SCANNER_HOME = tool name: 'SonarScanner',
                                    type: 'hudson.plugins.sonar.SonarRunnerInstallation'
            }
            steps {
                withSonarQubeEnv('SonarQube') {
                    bat "\"${SCANNER_HOME}\\bin\\sonar-scanner.bat\""
                }
            }
        }

        stage('7 - Quality Gate') {
            when {
                expression { !params.SKIP_SONAR }
            }
            steps {
                timeout(time: 10, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('8 - ML Training') {
            steps {
                dir("${BACKEND_DIR}") {
                    script {
                        echo "Training ${params.STANDARD}"
                    }
                }
            }
        }

        stage('9 - Export Metrics') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat '.venv\\Scripts\\python.exe ci\\export_metrics.py'
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'artifacts/prometheus_metrics.txt,artifacts/evaluation_summary.json,artifacts/drift_report.json',
                                     allowEmptyArchive: true
                }
            }
        }

        stage('10 - TrainingJob Update') {
            steps {
                dir("${BACKEND_DIR}") {
                    bat '.venv\\Scripts\\python.exe ci\\update_training_job.py'
                }
            }
        }

        stage('11 - Cleanup') {
            steps {
                cleanWs()
            }
        }
    }

    post {
        success {
            echo 'Pipeline SUCCESS'
        }
        failure {
            echo 'Pipeline FAILED'
        }
        always {
            echo "Build #${env.BUILD_NUMBER} terminé."
        }
    }

}
