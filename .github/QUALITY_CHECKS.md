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
| Spelling | `npx --yes cspell@8.19.4 --config cspell.json --no-progress "ReadMe.md" "CONTRIBUTING.md" "SECURITY.md" ".github/*.md" "frontend/README.md" "backend/**/*.md" "frontend/src/**/*.{js,jsx,css}" "backend/**/*.py"` | Source and documentation |
| Hygiene | `git diff --check <base> HEAD` | Whitespace and merge conflict markers |
| CI configuration | `cd backend && python -m unittest tests.test_ci_policy -v` | Parses workflow, Dependabot and issue template YAML; verifies job names, least-privilege permissions and mandatory PR checks |

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
**preserving both existing check names** because the active GitHub ruleset
requires both. To consolidate these workflows, a repository administrator must
first coordinate the ruleset/status-check change; otherwise merges can be
blocked unexpectedly.

Backend CI now installs the full pinned Python 3.11 runtime dependency set
along with separately pinned CI tools, then runs `pip check` before tests.
See [Python dependency policy](../backend/DEPENDENCIES.md). Workflow changes
also disable persisted checkout credentials, bound execution times, and cache
pip downloads.

The GitHub ruleset `main-require-all-ci` is **active** and requires seven PR
checks, including the frontend and backend dependency vulnerability scans.
It enforces strict up-to-date status checks, disallows bypasses, and protects
`main`. Verified via GitHub API on November 25, 2026. See
[Branch protection](BRANCH_PROTECTION.md) for the exact names, current review
threshold, and procedure for changing them. The ruleset currently requires
zero approving reviews; human approval is not mandatory.

Workflow and policy-file YAML is parsed by `tests.test_ci_policy` using the
already pinned `PyYAML` dependency, which retains the literal GitHub Actions
`on` key. The checks enforce a baseline contract; they do not replace
`actionlint` or validate GitHub's full workflow expression grammar.
