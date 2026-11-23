# Read-only admin dashboard

This dashboard is a separate operations view for the What Should I Eat? app.
It runs at **/admin** on the deployed Vercel frontend or locally at
`http://localhost:5173/admin` (with `npm run dev`).

## Configure on Render

In **Render > backend service > Environment**, add:

- `ADMIN_PASSWORD`: a unique, randomly generated secret **at least 16 characters long** (32+ characters recommended). Do not commit the secret or prefix it with `VITE_`.
- The existing `REDIS_URL`, `DATABRICKS_SERVER_HOSTNAME`,
  `DATABRICKS_HTTP_PATH`, and `DATABRICKS_PERSONAL_ACCESS_TOKEN` values
  remain server-side.
- `ADMIN_USERNAME` is **not used**; the current bootstrap administrator's
  username is fixed to `admin`.

Redeploy the backend after setting `ADMIN_PASSWORD`. **Without this setting
the admin login fails closed with HTTP 503.** No default password exists.

In Vercel, keep `VITE_API_URL` pointing to the backend base URL. The
`frontend/vercel.json` rewrite serves the client at `/admin`.

## Features

1. **Users & selections**: Redis username registry and the corresponding
   viewed, saved and tried recipe variants. These histories are scoped to
   the profile UUID. Up to 100 registered usernames and 30 cached recipes
   per history type are returned in a single request.
2. **Redis inspector**: read-only key metadata for `profile:username:v1:*`,
   `user:*` and `recipe:v2:*`. Returns up to 100 keys per request. No
   session tokens, Redis configuration, raw cache values or writes.
3. **Databricks events**: the latest 75 rows from either
   `default.app_user_events` or `default.user_clicks`. The queries are
   fixed and allowlisted. Recipe-details JSON and credentials are excluded.

All routes are restricted to an admin session. The browser stores its bearer
token only in **sessionStorage**; the backend stores only its SHA-256 digest in
Redis with an 8-hour TTL. Logging out revokes the session.

## Important boundaries

- This is an initial **single-admin, read-only diagnostic tool**, not a full
  production IAM system. Anyone who knows the password has access to user
  activity. Use a high-entropy secret, HTTPS, and restrict dashboard access
  to trusted administrators. Add SSO/MFA and audit logs before multi-admin
  production use.
- Failed login attempts are throttled (10 attempts per 15 minutes per
  apparent client IP); behind a reverse proxy, several clients could share
  that address.
- Usernames in the recipe app remain unauthenticated demo identifiers,
  **not secure individual user accounts**.
- Redis profile metadata is authoritative for this dashboard. Old unlinked
  accounts and evicted cached recipes may not be visible, and reads are
  intentionally bounded.
- Databricks errors return an unavailable message; the dashboard **cannot**
  execute ad hoc SQL or change data. Table creation and write permissions
  must be configured separately.
- No provider secrets or admin passwords belong in Vercel `VITE_*`
  variables; only the server may access Redis and Databricks credentials.

## Test

On a branch/PR, run backend tests:

```bash
cd backend
python -m unittest discover -s tests -v
```

After deploying, visit `/admin`, sign in with username `admin` and
your configured password, check the three tabs, sign out, and confirm
that an old bearer token no longer works. Never send admin credentials
or tokens in screenshots or issue reports.
