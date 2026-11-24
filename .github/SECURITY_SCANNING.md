# Dependency security scan policy

`.github/workflows/dependency-security.yml` runs on pull requests, pushes to
`main`, a weekly schedule and manual dispatch. It is intentionally separate
from the existing five protected checks (their exact names remain unchanged).

## What it checks

- **npm:** `npm ci --ignore-scripts` from the committed lockfile, followed by
  `npm audit --audit-level=high`. High/critical advisories fail; low/moderate
  findings remain visible in output and need triage, not silent acceptance.
- **Python:** `pip-audit==2.10.1` resolves `backend/requirements.txt` and
  fails if PyPI/OSV reports known vulnerabilities in the resolved packages.
  **Important:** backend requirements are currently unpinned, so this audits
  the dependency graph that a fresh resolver would select, NOT an immutable
  production release lockfile. Production may use different installed versions.
- No API keys or real Redis/Databricks/Gemini requests are needed. The workflow
  runs without privileged repository tokens or PR secrets.

## Triage

1. Open the failed job; record affected package, installed/resolved version,
   advisory identifier and fixed version.
2. Identify whether this is a direct or transitive dependency and whether the
   vulnerable feature is reachable; still treat all high/critical as blockers.
3. Upgrade the least disruptive compatible package, update the relevant
   manifest and lockfile (npm), rerun CI and tests. For Python, resolve and
   commit a reviewed production lock separately before claiming a reproducible
   deployment.
4. If upstream has no fix, open a tracked issue with owner, justification,
   mitigation and review date. Document any temporary exception explicitly in
   the PR, never hide it in an unconditional `|| true`.
5. Keep GitHub Dependabot alerts enabled if supported by repository settings.

## Protected branches

After observing a successful first run, repository admins should add
`Frontend dependency vulnerability scan` and
`Backend dependency vulnerability scan` to the required checks list.
Do not enable them until initial package findings are reviewed, otherwise
they may block merges. See `BRANCH_PROTECTION.md`.

## Developer commands

```sh
cd frontend && npm ci --ignore-scripts && npm audit --audit-level=high
python -m pip install pip-audit==2.10.1
python -m pip_audit -r backend/requirements.txt
```

The scanner queries advisory services and package registries; transient
network failures should be retried and diagnosed, not ignored.
