# Contributing

Thanks for improving **What Should I Eat?** This is a React/Vite + FastAPI application with Redis-backed demo profiles, Gemini recipe generation, optional Ollama/media integrations and optional Databricks analytics.

## Before you code

1. Read [README](ReadMe.md) for full-stack setup, API request schemas and known limitations.
2. Check [open issues](https://github.com/moreharsh/What_Should_I_Eat/issues) for a scoped task. Prefer one concern per pull request.
3. Create a descriptive branch from the latest `main` (for example, `fix/issue-123-brief-name`).
4. Never commit `.env`, provider keys, Redis URLs, Databricks tokens, session credentials or real profile activity. Use the provided `.env.example` files.

## Design expectations

- Keep request/response models and frontend API calls aligned. Reject invalid dietary input instead of treating it as unrestricted.
- Preserve diet-specific recipe caching: the same dish can have different cuisine/restriction variants.
- Keep viewed, saved and tried recipe actions separate. Username-only profiles are **demo identities, not secure accounts**.
- Treat every external system (Gemini, Redis, Databricks, YouTube, Spoonacular and Ollama) as fallible. Use bounded timeouts and safe user-visible errors. Do not invent recipe content when a model fails.
- Keep Databricks queries parameterized/allowlisted and analytics read-only in the admin UI.
- Add focused regression tests for bug fixes and user-facing behavior. Prefer mocked integration tests in CI; avoid live paid services.
- Accessibility matters: semantic controls, visible keyboard focus, meaningful status announcements, mobile layouts and high contrast.

## Local validation

Run these before requesting review:

```sh
# From repository root
python -m compileall -q backend
cd backend
python -m unittest discover -s tests -v
cd ../frontend
npm ci
npm run lint
node --test tests/*.test.mjs
npx --yes --package typescript@5.9.3 tsc --project jsconfig.json
npm run build
```

For isolated backend test dependencies, follow the exact installation commands in [README](ReadMe.md). CI also runs Python correctness lint and spelling/whitespace checks. [Quality checks](.github/QUALITY_CHECKS.md) explains each check.

## Pull request guidelines

- State **what** changed and **why**, and link the issue (`Closes #123` only when every acceptance criterion is met).
- Include how you tested, expected behavior, deployment or environment changes, screenshots for UI changes, and rollback considerations for risky changes.
- Avoid unrelated formatting churn, large generated binaries, and production credentials.
- Verify all checks are green; invite review before merging. Do not merge a failing PR or bypass protected-branch rules.
- If manual UI or external-service verification is outstanding, say so explicitly.

## Reporting vulnerabilities

Do **not** open a public issue containing a vulnerability exploit, private profile data or secrets. Follow [SECURITY.md](SECURITY.md) instead.

## Licensing

This repository does not currently declare a public license. Do not assume permission to redistribute or relicense its contents; maintainers can decide on a license separately.
