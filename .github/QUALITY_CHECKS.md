# Repository quality checks

The [Repository Quality](workflows/quality.yml) workflow runs on pull requests,
pushes to `main`, and manual dispatch. It requires no external AI, Redis,
Databricks, or deployment credentials.

| Check | How to run locally | Coverage |
| --- | --- | --- |
| Frontend lint | `cd frontend && npm ci && npm run lint` | Oxlint existing JS/JSX rules |
| Frontend type check | `cd frontend && npx --yes --package typescript@5.9.3 tsc -p jsconfig.json` | JavaScript and JSX via `checkJs` |
| Frontend build | `cd frontend && npm run build` | Vite production compilation |
| Python syntax | `python -m compileall -q backend` | Python syntax |
| Python lint | `ruff check backend --select E4,E7,E9,F63,F7,F82` | Errors and critical correctness rules; wider style lint can be introduced incrementally |
| Python tests | `python -m pip install -r backend/requirements.txt -r backend/requirements-ci.txt && cd backend && python -m unittest discover -s tests -v` | Mocked tests against pinned Python 3.11 runtime + CI dependencies |
| Spelling | `npx --yes cspell@8.19.4 --config cspell.json --no-progress "ReadMe.md" "CONTRIBUTING.md" "SECURITY.md" ".github/*.md" "frontend/README.md" "frontend/src/**/*.{js,jsx,css}" "backend/**/*.py"` | Source and documentation |
| Hygiene | `git diff --check <base> HEAD` | Whitespace and merge conflict markers |

**Limitations:** JavaScript `checkJs` checks the existing frontend without
requiring a TypeScript migration. Python lint deliberately starts with
critical correctness rules rather than enabling all formatting and typing rules
on previously unlinted code. The pipeline does not run paid API integration tests
or perform live integration tests. Runtime package vulnerabilities are checked
separately by `Dependency Security`, but supply-chain scanning is not exhaustive.
Dependencies are proposed via weekly
Dependabot PRs (npm, pip and GitHub Actions); these updates still need human
review and should never be automatically merged without testing.

Two backend-focused workflows currently run overlapping mocked suites. We are
**preserving both existing check names** until the active GitHub ruleset is
reviewed and updated. Removing either workflow prematurely could block
otherwise valid PRs.

Backend CI now installs the full pinned Python 3.11 runtime dependency set
along with separately pinned CI tools, then runs `pip check` before tests.
See [Python dependency policy](../backend/DEPENDENCIES.md). Workflow changes
also disable persisted checkout credentials, bound execution times, and cache
pip downloads.

After this workflow is merged and its checks are green, protect `main` under
GitHub repository Settings → Rules → Rulesets and require the checks
`Frontend lint, types, build`, `Backend syntax, lint, tests`,
`Spelling (CSpell)`, `Git whitespace and conflict markers`, and
`dietary-cache-tests`. Optionally also require both dependency vulnerability
scans after reviewing the initial baselines. The ruleset is **not currently
enforced**; a repository administrator must enable it.
