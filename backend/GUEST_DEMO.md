# One-click Guest User demo mode (Issue #51)

The login screen includes **Continue as Guest** in addition to registered-account
sign-in and sign-up. Clicking it immediately requests
`POST /api/guest-session` with no username, password, email or identity
parameters. The backend issues a random UUID, a short-lived bearer token and
the **exact display name `Guest User`**. That display name is not an account
name, Redis identity lookup, or shared credential. Each click that starts a
new session produces a distinct UUID and token.

## Persistence and privacy

- The guest bearer session has a **30-day maximum TTL**, remains accessible
  through a valid token stored in this browser, and can resume after a reload.
  No sliding extension is promised. Redis stores a SHA-256 digest of the bearer
  token as the session key; the raw token is never logged or exposed by admin.
- **Exit Guest** revokes the token and clears client state; choosing Guest again
  creates a new UUID and **does not restore** the old history. Clearing browser
  storage or token expiration likewise prevents recovery.
- Viewed, saved and tried history remains isolated under the existing
  `user:{uuid}:*:v2` keys, while recipe cache entries are shared strictly by
  canonical dish, cuisine and dietary restriction variants. A view does not
  imply a save or cooking.
- **Keep my recipes** upgrades the currently authenticated guest UUID into
  a registered account via `POST /api/auth/register`, with a new valid
  username/password and one-time recovery code. No guest names or expired
  tokens can be used to claim another session's records.
- Guest activity may appear in authenticated administrator profile and
  Databricks event views as `Guest User`, associated with a unique opaque UUID.
  Demo bot/activity counts are not verified unique humans. Account password,
  recovery code and raw bearer token never enter analytics.

## Abuse controls and failure states

The guest endpoint is limited to **10 new sessions per client address per
15 minutes** via a hashed client-address Redis key. Guest User model
requests with a valid guest bearer token are capped at **40 menu requests**
and **20 recipe requests** per guest UUID per 24-hour fixed TTL window.
Existing public `/api/menu` anonymous compatibility is preserved; these
controls are *not* a replacement for upstream gateway-wide quotas and
provider-budget alerts. A registered account does not inherit guest demo
quota counters after upgrading.

Redis connectivity failure returns 503 rather than issuing a fake session.
Guest quota exhaustion returns 429. The frontend shows retryable errors and
disables duplicate guest submissions. Rate-limit counters have Redis TTLs;
the admin Redis inspector does not expose bearer session keys or raw tokens.

## Production verification

1. Visit the site without credentials and click **Continue as Guest**.
   The header shows **Guest User**. Choose cuisine, generate/open recipes,
   and explicitly save/mark tried.
2. Reload in the same browser. The current guest session should restore
   its history when selecting the same cuisine/variant.
3. In a second isolated browser context, click Guest again. Its viewed,
   saved and tried sets must be empty; it cannot read the first UUID's data.
4. **Exit Guest** in the first browser. The former bearer token is revoked;
   another Guest click starts with new empty history.
5. Create an account with **Keep my recipes** while holding a valid guest
   session, save the displayed recovery code, sign out and sign in to verify
   the same UUID and recipe history.
6. Verify the separate admin password is required for `/api/admin/*` and
   no raw bearer token appears there. Check 429/503 guest states using mocked
   integration tests; do not intentionally exhaust shared production quotas.

No new environment variables, paid services, or Databricks schema changes.
Deploy backend before frontend so the new guest button has an available route.
