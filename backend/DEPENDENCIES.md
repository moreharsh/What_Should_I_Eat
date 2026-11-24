# Python dependency reproducibility (Python 3.11)

## Files and purpose

- `requirements.in`: concise list of direct application dependencies,
  intentionally not used as a deploy or CI installation input.
- `requirements.txt`: **66 pinned direct and transitive packages** obtained
  by running `python -m pip install -r backend/requirements.in` and
  `python -m pip freeze --exclude-editable` on a GitHub-hosted Ubuntu
  Linux runner with Python 3.11 (November 24, 2026).
- `requirements-ci.txt`: exact pinned CI-only tools (Ruff and httpx2).
  This is installed alongside the pinned runtime requirements in the existing
  backend quality and dietary regression workflows.

This is version reproducibility, **not full bit-for-bit build
reproducibility**: package file hashes are not enforced and Python/OS/CPU
platform differences can select different wheels. The current snapshot
targets Linux x86_64 and CPython 3.11. Do not use this snapshot on
unverified Python versions (e.g. Python 3.13). Keep the Python version on
Render aligned with 3.11 and verify the build logs after merging.

## Local setup

Use Python 3.11 in an isolated virtual environment:

```sh
cd backend
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-ci.txt
python -m pip check
python -m unittest discover -s tests -v
```

For runtime-only setup, omit `requirements-ci.txt`.

## Updating the snapshot

1. Edit the direct application inputs in `requirements.in`.
2. Create a **fresh** Python 3.11 Ubuntu Linux environment (a GitHub
   Actions job is recommended).
3. Install with `python -m pip install -r requirements.in`, then run
   `python -m pip freeze --exclude-editable` to produce a candidate list
   including all transitive dependencies. Exclude only unrelated tooling
   that was present before the runtime install. **Do not** mix runtime
   snapshots with dev/test tools added separately.
4. Compare the candidate to `requirements.txt` and review major-version
   shifts and transitive changes. Update all version pins in one reviewed PR.
5. Install from `requirements.txt` in a clean environment and run
   `python -m pip check`, all mocked unit tests, Ruff and `pip-audit`.
6. Review deployment build logs and smoke tests after merging.
7. For Python/toolchain version changes, regenerate from scratch and review
   separately. Don't silently rely on a stale lock.

**Note:** Existing CI tests use mocks, so they do not guarantee live
Gemini/Databricks/Redis compatibility. Validate affected integrations
manually when changing their SDKs or connectors.

## Dependency upgrades and Dependabot

Dependabot may propose updates to the many explicit pins in
`requirements.txt`. Review them as a complete resolved set and verify
the same requirements work on Python 3.11. Make any needed corresponding
direct-input change in `requirements.in`. Do not merge a PR that breaks
mock tests, runtime installation or the vulnerability scanner.

## Deployment note

The repository does not define Render's service settings in a
`render.yaml`, so the Render dashboard's Python version and build command
must be verified by the owner. The backend installation should use the
pinned `backend/requirements.txt` relative to the configured root
directory. This PR does **not** automatically change Render settings.
