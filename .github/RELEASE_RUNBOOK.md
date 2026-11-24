# Deployment verification and rollback runbook

## What is actually deployed

- The frontend is hosted by Vercel, and the FastAPI backend by Render.
- GitHub PR checks validate local/mock behavior; they do not test live Gemini,
  Redis or Databricks credentials and cannot guarantee successful deployment.
- `Production API smoke test` runs **after pushes to main**, and manually.
  It uses the existing GitHub Actions repository variable `BACKEND_BASE_URL`
  to call only the public `GET /api/health` endpoint. It does not use secrets,
  incur paid AI requests, or write to Redis.
- **Limitation:** A passing API health check means the endpoint was reachable,
  NOT that Render deployed the latest commit. The smoke job may reach the
  previous version while Render is still deploying.

## Release checklist

1. Review code changes and dependency advisories in the PR.
2. Confirm all five existing CI checks and both dependency scans are green.
3. Merge only after protected-main rules allow it.
4. Check the Vercel and Render deployment dashboards for the expected commit.
5. Inspect the smoke workflow run and confirm Render reports a successful
   deployment of that same commit.
6. Perform a read-only admin/dashboard check, then optionally a controlled
   user recipe test if the release changes recipe behavior. Do not generate
   billable AI content in automated PR checks.
7. Monitor Render logs and the Redis heartbeat scheduled workflow.

## If the release is broken

1. Identify the failing deployment and last known good commit.
2. Prefer platform-native rollback/redeploy of the last known good Vercel or
   Render deployment. Follow the provider UI instructions and verify the
   committed revision; do not assume a GitHub `git revert` instantly
   rolls back a hosted service.
3. If needed, revert the offending PR through a new reviewed PR, then rerun
   all CI and recheck deployments.
4. Confirm `GET /api/health`, app UI, and affected user flows after rollback.
5. Document the incident, impacted features, cause and follow-up tests.

## Enforcement and limitations

The smoke job runs on `push: main` (not on untrusted PRs), with read-only
permissions and no deployment credentials. Do NOT mark it as a required PR
check; it intentionally does not run on PRs. `BRANCH_PROTECTION.md`
documents the five existing PR checks and how an admin can add dependency
security scan checks after they are consistently green.

To prove the currently deployed backend revision, add a trusted deployment
integration with a commit SHA and provider callback in a separate, reviewed
follow-up. Never send Render/Vercel deployment tokens to PR workflows.
