pipeline {
    agent any
    parameters {
        string(name: 'PYTHON_EXECUTABLE', defaultValue: 'python3', description: 'Python 3.12+ interpreter on the agent')
    }
    options {
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 20, unit: 'MINUTES')
    }
    environment {
        // Python 3.12+ must be available on the trusted, dedicated Jenkins agent.
        PYTHON = "${params.PYTHON_EXECUTABLE}"
        PIP_CACHE_DIR = "${WORKSPACE}/.pip-cache"
        AILP_RUNTIME = "${WORKSPACE}/runtime"
    }
    triggers { pollSCM('H/5 * * * *') }
    stages {
        stage('Build') {
            steps {
                sh '''
                  set -eu
                  mkdir -p reports
                  "$PYTHON" -m venv .venv
                  .venv/bin/python -m pip install -r requirements-dev.txt
                  rm -rf dist build
                  .venv/bin/python -m build --wheel
                  .venv/bin/python scripts/checksum.py
                '''
            }
        }
        stage('Test') {
            steps {
                sh '.venv/bin/python -m pytest --cov=ailp --cov-branch --cov-fail-under=85 --cov-report=xml:reports/coverage.xml --junitxml=reports/junit.xml'
            }
            post { always { junit 'reports/junit.xml' } }
        }
        stage('Code Quality') {
            steps {
                sh '''
                  .venv/bin/ruff check ailp tests scripts --output-format json > reports/ruff.json
                  .venv/bin/ruff format --check ailp tests scripts
                '''
            }
        }
        stage('Security') {
            steps {
                sh '''
                  .venv/bin/bandit -r ailp scripts -f json -o reports/bandit.json
                  .venv/bin/pip-audit -r requirements.txt --format json --output reports/dependency-audit.json
                '''
            }
        }
        stage('Deploy') {
            steps {
                sh '''
                  .venv/bin/python scripts/deploy.py staging "build-${BUILD_NUMBER}-${GIT_COMMIT}"
                  .venv/bin/python scripts/smoke.py
                '''
            }
        }
        stage('Release') {
            when { expression { env.BRANCH_NAME == 'main' || env.GIT_BRANCH == 'origin/main' } }
            steps {
                sh '''
                  .venv/bin/python scripts/deploy.py production "build-${BUILD_NUMBER}-${GIT_COMMIT}"
                  .venv/bin/python scripts/release_record.py
                '''
            }
        }
        stage('Monitoring') {
            when { expression { env.BRANCH_NAME == 'main' || env.GIT_BRANCH == 'origin/main' } }
            steps {
                sh '''
                  .venv/bin/python scripts/monitor.py incident
                  .venv/bin/python scripts/monitor.py start
                '''
            }
        }
    }
    post {
        always { archiveArtifacts artifacts: 'dist/*.whl,reports/*', fingerprint: true, allowEmptyArchive: true }
        failure { echo 'Pipeline failed. Inspect archived reports. Release readiness failures restore the previous healthy service.' }
    }
}
