# Security policy

## Reporting a vulnerability

Please **do not submit vulnerabilities, credentials, private profile information or exploit instructions in public GitHub issues**.

If GitHub's **Report a vulnerability** / private vulnerability reporting option is available under the repository's **Security** tab, use it. Otherwise contact the repository maintainer privately through their existing GitHub profile contact options. Do not paste secrets in the report.

Include the affected commit/version, impact, reproduction steps (without real user data), and a safe demonstration. We will assess reports and coordinate a fix before public disclosure. No specific response-time SLA is promised.

## Scope and important limitations

- The username-based recipe profile is **demo-only and has no password**. Entering another user's username can open that profile. Do not store confidential or sensitive data in recipes/history; production use requires real authentication.
- The admin dashboard uses one separately configured high-entropy password and short-lived sessions. It is not a complete SSO/MFA or multi-role identity system.
- AI-generated recipes may contain mistakes. They are not medically verified for allergens, ingredient contamination or dietary restrictions.
- External provider API keys, Redis URLs, Databricks credentials and administrator secrets belong only in backend runtime configuration; **never** in frontend `VITE_*` variables.
- Optional Ollama must run behind trusted access controls; do not expose an unauthenticated inference service on the public internet.
- CI should use mocked services and must never print credentials or user data.

## Dependencies and security fixes

Review Dependabot PRs and security warnings regularly. Confirm changed dependencies are compatible with Python 3.11 / Node 22 and existing backend/frontend regression tests before merging. Rotate credentials immediately if they are accidentally disclosed.
