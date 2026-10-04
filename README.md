# AI Learning Passport DevOps project

This project extends the AILP design concept with a working Flask API, SQLite persistence,
seven browser views, explicit consent, role authorization, and a seven-stage Jenkins pipeline.
The earlier visual prototype is at https://ailp-sit223-learning-passport.ashriya-singla2.chatgpt.site/.
That hosted prototype is design context, not the application deployed by this Jenkinsfile.

## Requirements

- A dedicated trusted macOS or Linux Jenkins agent with Python 3.12 or newer, Git and pip.
- Jenkins LTS with Pipeline, Git, JUnit and Pipeline Stage View plugins.
- Network access to PyPI and the vulnerability advisory service.
- Free loopback ports 8081 (staging) and 8082 (local production demonstration).

This assessment uses two local environments. Production is a release environment on the
assessment host, not an internet production service. One student and one educator role are
supported. Real student data, multi-user accounts, TLS and university SSO are outside this demo.

## Jenkins setup from GitHub

1. Clone this repository, or create a Jenkins Multibranch Pipeline directly from its GitHub URL.
2. In Jenkins, add the Git branch source and select this repository. Use `Jenkinsfile` as the script path.
3. Scan the repository. Build `main`; feature branches run checks and staging, while release and
   monitoring run only on `main`. Configure `PYTHON` in the Jenkinsfile for your agent if needed.
4. All seven eligible stages must be green. Jenkins archives the wheel, checksums and reports.
5. Open http://127.0.0.1:8081/ for staging and http://127.0.0.1:8082/ for the local release.
6. Role tokens are generated at deployment in `runtime/credentials.json` with owner-only permissions.
   Read that file locally, enter the appropriate token in the application's role token field, and
   do not include tokens in screenshots, Git or assessment uploads.

SCM polling checks every five minutes. A GitHub webhook can replace polling when Jenkins is
reachable through an appropriately secured endpoint. Jenkins stays on loopback in this setup.

## Seven stages

| Stage | Gate and output |
|---|---|
| Build | Isolated environment, pinned tools, deployable wheel and SHA-256 identity |
| Test | Pytest behaviour/authorization tests, JUnit XML, branch coverage gate >=85% |
| Code Quality | Ruff style, correctness, import and complexity checks (maximum 10), format gate |
| Security | Bandit source scan and pip-audit pinned runtime dependency scan; nonzero exits block release |
| Deploy | Versioned wheel installed in staging, readiness polling, HTTP consent/CRUD smoke test |
| Release | Promote the same staged version to a separate production process/database; readiness failure restores previous release |
| Monitoring | Actual production outage drill, FIRING and RESOLVED alert records, health metrics, continuous five-second checks |

Monitoring is a custom Python health monitor. It checks `/health` with a two-second timeout,
alerts after two consecutive failures and records recovery. The local alert inbox is
`runtime/alerts.jsonl`; the continuous service log is `runtime/monitor.log`.
No external email or team notification service is configured. This is an explicit limitation.

## Local development

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest --cov=ailp --cov-branch --cov-fail-under=85
.venv/bin/ruff check ailp tests scripts
.venv/bin/ruff format --check ailp tests scripts
.venv/bin/bandit -r ailp scripts
.venv/bin/pip-audit -r requirements.txt
.venv/bin/python -m build --wheel
mkdir -p reports
.venv/bin/python scripts/checksum.py
.venv/bin/python scripts/deploy.py staging manual-1
.venv/bin/python scripts/smoke.py
.venv/bin/python scripts/deploy.py production manual-1
.venv/bin/python scripts/monitor.py incident
.venv/bin/python scripts/monitor.py start
```

The incident drill briefly stops the local release; use it only on the demonstration environment.
Deployments retain old release directories. Do not delete these while their service is running.
To stop a service, call `stop('staging')` or `stop('production')` from `scripts/deploy.py`.
Terminate the PID from `runtime/monitor.pid` to stop the monitor.

## Evidence and assessment

Use actual Jenkins screenshots and archived reports. The Trello board, Idea Canvas and 7.2D
reflection are prior design context, not evidence of successful pipeline execution.
The PDF answer sheet must include the GitHub URL, seven stage descriptions and Jenkins evidence.
The user is recording the required video separately (maximum ten minutes).
Grant both marker and unit chair access if the repository is private.

## References

- Jenkins pipeline: https://www.jenkins.io/doc/book/pipeline/
- Test and artifact recording: https://www.jenkins.io/doc/pipeline/tour/tests-and-artifacts/
- Flask testing: https://flask.palletsprojects.com/en/stable/testing/
- Ruff: https://docs.astral.sh/ruff/
- Bandit: https://bandit.readthedocs.io/
- pip-audit: https://github.com/pypa/pip-audit
