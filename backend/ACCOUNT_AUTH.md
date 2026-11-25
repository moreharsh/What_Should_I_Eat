# Persistent recipe accounts — authentication contract

Issue #50 adds registered accounts to the existing anonymous-session backend.
The client offers **Sign in**, **Sign up**, **Temporary demo**, and a one-time
**Keep my recipes** upgrade for an anonymous session that is still active.
Guest-without-username entry remains tracked separately under Issue #51.

## Account identity and storage

- `POST /api/auth/register`: username (3–24 letters/numbers/underscores) and
  password (12–256 characters). Creates a normalized unique username account
  and a stable UUID. Returns an authenticated token **and a high-entropy
  one-time recovery code** shown only at registration.
- `POST /api/auth/login`: checks the Argon2id password hash and restores the
  **same UUID**, even from another device. An expired/revoked session never
  deletes the account or viewed/saved/tried history.
- `POST /api/auth/logout`: revokes the current token; `GET /api/auth/me`:
  requires a valid session.
- `POST /api/auth/recover`: username, saved recovery code and new password.
  Consumes that code once, rotates to a new one, and invalidates prior
  registered account sessions. Without a saved recovery code, **recovery is
  not possible yet**; no verified-email delivery mechanism is available.
- `POST /api/session` remains for temporary anonymous profiles.
  `GET /api/session` and `DELETE /api/session` remain compatible with existing
  browser bearer sessions.

The backend stores account details under `account:user:v1:{uuid}` and the
lowercased username→UUID under `account:username:v1:{name}`. A fixed Redis
Lua script allocates the username, account record, and account-ownership key
atomically to reject concurrent collisions and duplicate guest claims. Passwords
are never stored in plaintext: `argon2-cffi` uses Argon2id. Tokens are random;
**new registered session Redis keys use SHA-256 of the token**, so reading Redis
key names does not reveal them. A session-generation key invalidates all
previous account tokens after recovery without enumerating sessions.
Rate limits are applied to registration, login and recovery.

## Safe anonymous migration

If registration is sent with a **currently valid anonymous bearer token**,
the account adopts that UUID; current viewed, saved and tried Redis sets
remain in place. Signing up with the username alone does not claim any data.
Pre-PR #49 profiles that are recorded in the old shared-username registry
cannot be upgraded automatically because multiple people may hold tokens.
The user must instead create a fresh account; **do not auto-merge or copy**
historical records across identities.

Existing sessions survive deployment, and historic Redis profile/history
records are not deleted. The new `account:*` namespace is deliberately
excluded from the admin Redis inspector, so password hashes and recovery-code
hashes are not exposed by admin API routes or Databricks.

## Threat model and limits

The server derives user IDs from bearer sessions, never request-body
identifiers. Separate account UUIDs have distinct recipe histories. Username
matching is case-insensitive; registering an already registered username
returns a conflict. Authentication responses use generic credential errors;
repeated attempts are throttled. Production requires HTTPS and server-side
Redis persistence/backup. Browser storage still holds a bearer token and is
vulnerable to XSS if the site becomes compromised. Account management,
verified-email recovery, MFA, and self-service deletion require future review.

**Before merging:** all mocked tests and dependency audits must pass.
Check registration/login/recovery on a preview deployment with a test Redis.
Roll out backend before the new frontend; revert both if necessary. Confirm an
existing anonymous session retains its history, can be upgraded with its token,
and cannot be claimed using just the same username. After deploy, test sign-in
from an incognito browser restores the same UUID and saved/tried/viewed recipes.
Never log or screenshot real recovery codes or production tokens.
