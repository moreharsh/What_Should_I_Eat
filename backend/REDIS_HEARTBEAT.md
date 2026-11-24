# Redis Cloud Free heartbeat

Redis Cloud can delete inactive Free/evaluation databases. This feature issues a
small real Redis write to a dedicated metadata key on a schedule, without
modifying recipe caches, usernames, saved/tried history, or sessions.

This is intended **only for a demo/development Redis instance**. It does not
guarantee retention, backups, or production availability. Prefer a paid plan and
external backups for important data. Scheduled GitHub Actions workflows can be
delayed or disabled for inactive repositories; monitor each run.

## API contract

- `POST /api/maintenance/redis-heartbeat`: update
  `maintenance:redis-heartbeat:last-updated-utc` to the current UTC ISO timestamp.
  Returns `{"status":"ok","last_updated_utc":"..."}`.
- `GET /api/maintenance/redis-heartbeat`: read the existing timestamp **without
  modifying the timestamp**. Returns `last_updated_utc: null` before first write.
- Both endpoints require `X-Heartbeat-Token` with a separately configured
  `REDIS_HEARTBEAT_TOKEN` of at least **32 characters**.
- Missing/wrong/unconfigured token => HTTP 401; Redis failures => HTTP 503.
  The response never exposes the Redis URL, password, or connection details.

The `GET` may itself count as Redis read activity, but using `POST` for the
explicit maintenance write keeps HTTP semantics and last-updated meaning clear.

## Setup (GitHub Actions + Render)

1. Generate a unique secret of at least 32 random characters locally; for
   example, `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
2. Set the **same value** as `REDIS_HEARTBEAT_TOKEN` in Render's backend
   environment variables and in GitHub repository **Settings → Secrets and
   variables → Actions → Secrets**. Never put this in `VITE_*` variables.
3. In GitHub repository **Settings → Secrets and variables → Actions →
   Variables**, set `BACKEND_BASE_URL` to your deployed backend's
   `https://` origin, e.g. `https://your-api.example.com`. Do not include
   the `/api/maintenance/...` path.
4. Redeploy/restart Render after setting the backend secret.
5. Go to **Actions → Redis Cloud activity heartbeat → Run workflow** and
   verify the run succeeds. Review the operation's response or inspect the
   saved timestamp with an authenticated GET.
6. Leave the scheduled workflow enabled. It runs on Mondays and Thursdays,
   at 10:17 UTC. Monitor failure notifications; never assume a cron run is
   sufficient if Redis is unavailable or your Render app is suspended.

### Local/manual calls

```sh
# Shell environment variables should be set securely, never committed.
curl --fail-with-body --request POST \
  --header "X-Heartbeat-Token: ${REDIS_HEARTBEAT_TOKEN}" \
  "${BACKEND_BASE_URL%/}/api/maintenance/redis-heartbeat"

curl --fail-with-body \
  --header "X-Heartbeat-Token: ${REDIS_HEARTBEAT_TOKEN}" \
  "${BACKEND_BASE_URL%/}/api/maintenance/redis-heartbeat"
```

A successful HTTP 200 reflects that Redis acknowledged the write. The
`/api/health` endpoint alone does **not** prove Redis activity.

Tests use a mocked Redis client and do not require Redis Cloud credentials.
