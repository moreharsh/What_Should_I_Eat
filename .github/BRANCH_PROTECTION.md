# Protect `main` with mandatory CI checks

> Verified November 25, 2026: repository ruleset **`main-require-all-ci`** (ID 27958242) is active, targets the default branch, requires up-to-date status checks and pull requests, and has no bypass actors. This document also serves as a recovery checklist if the ruleset is changed.

## Existing ruleset and recreation instructions

1. Open **Settings → Rules → Rulesets → New ruleset → New branch ruleset**.
2. Name it `main-require-all-ci` and set **Enforcement status: Active**.
3. Under **Target branches**, add the repository's default branch (`main`).
4. Enable **Require a pull request before merging**.
5. Enable **Require status checks to pass** and select **all seven** exact job/check names (current verified configuration):
   - `Frontend lint, types, build`
   - `Backend syntax, lint, tests`
   - `Spelling (CSpell)`
   - `Git whitespace and conflict markers`
   - `dietary-cache-tests`
   - `Frontend dependency vulnerability scan`
   - `Backend dependency vulnerability scan`
6. Enable **Require branches to be up to date before merging** (strict), unless you use a merge queue. If you enable a merge queue, add `merge_group` triggers to both workflows.
7. Disallow force pushes and branch deletion; select **Do not allow bypassing** (or keep the bypass list empty). Verify the rule covers administrators and other privileged actors as intended.
8. **Create** the ruleset and confirm its state is **Active**.

All seven required jobs run on every PR, including docs-only changes. The dietary workflow intentionally has **no `paths` filter**; a skipped required workflow can leave merges permanently pending.

If these check names do not appear, open a PR to trigger the workflows and then return to the ruleset editor.

## Verify enforcement

1. Open a PR with a harmless change and ensure all seven checks appear.
2. Temporarily submit a PR with a deliberate lint or spelling error. The merge button should remain blocked until that check passes.
3. Remove the test error and verify all checks run again and the PR becomes mergeable.
4. Try a direct push to `main` only if it is safe and authorized; the ruleset should refuse pushes that bypass required PR review.

## Security checks and change control

Both dependency security checks are **already required** in the active ruleset. Treat high/critical advisory failures as blockers and follow [security scanning triage](SECURITY_SCANNING.md). Before removing or renaming any job, update the active ruleset in a coordinated administrator action. The `Public backend availability` job runs on `main` pushes only, so **do not** require it for PRs. See [release runbook](RELEASE_RUNBOOK.md).

## What this does not cover

- The `Vercel` deployment status is separate and is **not** one of the current seven required checks. A repository administrator may add it after reviewing deployment behavior and failures.
- The Python quality job runs mocked API tests and restricted Ruff rules. It does not run production Redis, Gemini/AI, or Databricks integration tests.
- GitHub rulesets, unlike guidance in this file, enforce protected-main rules. The connected GitHub integration can read existing ruleset settings but cannot make administrator-level changes.

## Local commands

```sh
cd frontend && npm ci && npm run lint && npm run build
cd ../backend && python -m unittest discover -s tests -v
```

## Verified ruleset details (November 25, 2026)

GitHub API confirmed ruleset ID `27958242` is `active`, targets `~DEFAULT_BRANCH`, requires pull requests and all seven checks listed above, enables strict (up-to-date) checks, disallows force pushes and deletion, and has no bypass actors. The pull request rule currently requires **zero approving reviews**; it requires review-thread resolution, but zero approvals is not the same as mandatory human code review. A repository administrator should decide whether to require at least one approval when an independent reviewer is available. Do not enable an approval count that would make a solo-maintained repository impossible to update. Re-verify settings after any change.
