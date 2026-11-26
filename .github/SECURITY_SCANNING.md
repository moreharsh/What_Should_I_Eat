# Dependency security scan policy

`.github/workflows/dependency-security.yml` runs on pull requests, pushes to
`main`, a weekly schedule and manual dispatch. It is separate from the five quality/dietary checks, but **both dependency scan jobs are now required** by the active `main-require-all-ci` ruleset (verified November 25, 2026).

## What it checks

- **npm:** `npm ci --ignore-scripts` from the committed lockfile, followed by
  `npm audit --audit-level=high`. High/critical advisories fail; low/moderate
  findings remain visible in output and need triage, not silent acceptance.
- **Python:** `pip-audit==2.10.1` checks the pinned Python 3.11 dependency
  snapshot in `backend/requirements.txt` and fails on known vulnerabilities.
  This is a complete version-pin snapshot, **not a hash-locked wheel archive**;
  platform-specific artifacts and separately deployed revisions must still
  be verified on Render.
- No API keys or real Redis/Databricks/Gemini requests are needed. The workflow
  runs without privileged repository tokens or PR secrets.

## Triage

1. Open the failed job; record affected package, installed/resolved version,
   advisory identifier and fixed version.
2. Identify whether this is a direct or transitive dependency and whether the
   vulnerable feature is reachable; still treat all high/critical as blockers.
3. Upgrade the least disruptive compatible package. For npm, update the
   manifest and lockfile. For Python, update the direct requirement in
   `backend/requirements.in` and regenerate/review the full pinned
   `backend/requirements.txt` snapshot on Python 3.11. Rerun tests and audits.
4. If upstream has no fix, open a tracked issue with owner, justification,
   mitigation and review date. Document any temporary exception explicitly in
   the PR, never hide it in an unconditional `|| true`.
5. Keep GitHub Dependabot alerts enabled if supported by repository settings.

## Protected branches

The active repository ruleset **already requires** both
`Frontend dependency vulnerability scan` and
`Backend dependency vulnerability scan`. Any high/critical advisory may block merging; triage it as above rather than removing the check. See `BRANCH_PROTECTION.md` for the full list of seven required checks.

## Developer commands

```sh
cd frontend && npm ci --ignore-scripts && npm audit --audit-level=high
python -m pip install pip-audit==2.10.1
python -m pip_audit -r backend/requirements.txt
```

The scanner queries advisory services and package registries; transient
network failures should be retried and diagnosed, not ignored.
