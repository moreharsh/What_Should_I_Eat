# Protect `main` with mandatory CI checks

> This file is guidance. **Merging is not blocked by a workflow YAML file alone.**
> A repository admin must activate the GitHub ruleset described below.

## Set up the ruleset

1. Open **Settings → Rules → Rulesets → New ruleset → New branch ruleset**.
2. Name it `main-require-all-ci` and set **Enforcement status: Active**.
3. Under **Target branches**, add the repository's default branch (`main`).
4. Enable **Require a pull request before merging**.
5. Enable **Require status checks to pass** and select **all five** exact job/check names:
   - `Frontend lint, types, build`
   - `Backend syntax, lint, tests`
   - `Spelling (CSpell)`
   - `Git whitespace and conflict markers`
   - `dietary-cache-tests`
6. Enable **Require branches to be up to date before merging** (strict), unless you use a merge queue. If you enable a merge queue, add `merge_group` triggers to both workflows.
7. Disallow force pushes and branch deletion; select **Do not allow bypassing** (or keep the bypass list empty). Verify the rule covers administrators and other privileged actors as intended.
8. **Create** the ruleset and confirm its state is **Active**.

All five jobs run on every PR, including docs-only changes. The dietary workflow intentionally has **no `paths` filter**; a skipped required workflow can leave merges permanently pending.

If these check names do not appear, open a PR to trigger the workflows and then return to the ruleset editor.

## Verify enforcement

1. Open a PR with a harmless change and ensure the five checks appear.
2. Temporarily submit a PR with a deliberate lint or spelling error. The merge button should remain blocked until that check passes.
3. Remove the test error and verify all checks run again and the PR becomes mergeable.
4. Try a direct push to `main` only if it is safe and authorized; the ruleset should refuse pushes that bypass required PR review.

## What this does not cover

- The `Vercel` deployment status is separate. Add `Vercel` as a sixth required status check if deployment success must gate merging.
- The Python quality job runs mocked API tests and restricted Ruff rules. It does not run production Redis, Gemini/AI, or Databricks integration tests.
- Workflow configuration itself has no permission to enforce branch protection. The GitHub connection used for this PR cannot write repository rulesets.

## Local commands

```sh
cd frontend && npm ci && npm run lint && npm run build
cd ../backend && python -m unittest discover -s tests -v
```
