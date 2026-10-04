# Security scope and findings

The service is bound to localhost, uses separate randomly generated role tokens, rejects empty
or identical credentials, validates JSON input and import consent, and uses parameterized SQLite
queries. Browser rendering uses `textContent` rather than injecting evidence as HTML. The browser
does not persist tokens. A Content Security Policy restricts scripts and styles to same-origin files.

## Source scan review

The initial Bandit scan reported seven findings in deployment tools: two low-severity B404
subprocess-import notices, two low-severity B603 subprocess-call notices, and three medium-severity
B310 URL-open notices. None was an application SQL injection or authorization defect.

Each suppressed line was reviewed. B404/B603 calls execute the trusted Python interpreter and
fixed pip/venv/Gunicorn commands using argument arrays without a shell. Version strings are
validated before paths are constructed. B310 calls use literal loopback HTTP URLs; the smoke
script accepts paths only from its internal fixed calls. No URL is supplied by an application user.
Narrow `nosec` annotations retain this justification rather than disabling a category globally.
Remove the annotations and re-review if these tools ever accept untrusted executables or URLs.

## Remaining limitations

- This is a single-student assessment service, not a deployed university system.
- Tokens are bearer credentials; SSO, rotation, rate limits and multi-user ownership are future work.
- TLS is required before exposing the service remotely. The supplied deployment binds only to localhost.
- A dedicated trusted Jenkins agent is assumed. Do not run untrusted pull-request jobs on this agent.
- SQLite backups, encryption at rest and retention schedules need production planning.
- Monitoring alerts stay in a local inbox. External team notification requires a separately configured destination.
- A passing dependency audit means no known advisories at scan time, not proof of absence of vulnerabilities.
