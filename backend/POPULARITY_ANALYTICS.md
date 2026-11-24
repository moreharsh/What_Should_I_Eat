# Recipe popularity analytics

Admin-only aggregated charts in `/admin` → **Recipe popularity**.

## Sources and exact meanings

| Chart | Table | Filter | Unit |
| --- | --- | --- | --- |
| Most opened recipes | `default.user_clicks` | `tracking_context` in `CachedCuisine`, `DiscoveryFeed` | Recipe-open log events |
| Most viewed cuisines | `default.app_user_events` | `event_type = 'viewed'` | Recipe-view events |

**These are not unique users or unique sessions.** Repeated recipe opens
count repeatedly. The two charts use different, independently logged
tables, so their numbers should not be summed or compared as a conversion
funnel. A 'cuisine preference' here means *cuisine of viewed recipes*,
**not** a declared favorite or saved/tried preference.

The existing logged records may not have complete historical coverage
because Databricks writes are best effort. Counted events occur at or
after `CURRENT_TIMESTAMP() - INTERVAL N DAYS`, measured by the Databricks
warehouse's UTC clock. Supported windows: 7, 30, 90 days.

## API and security

`GET /api/admin/popularity?days=30` requires the same short-lived
Redis-backed admin bearer session as the other `/api/admin/*` endpoints.

- Only fixed, source-allowlisted `SELECT ... COUNT(*) ... GROUP BY` SQL
  statements run. The numeric timeframe must be exactly 7, 30, or 90;
  it cannot inject SQL or select another table.
- The SQL warehouse aggregates server-side. The browser receives at most
  ten rows per chart with `{label, count}` and no usernames, user IDs,
  raw events, credentials, SQL, or recipe text.
- Records sort by event count descending and label ascending for ties.
- No new tables, Redis keys, or secrets are required.
- Missing credentials or an unavailable/missing SQL table/warehouse return
  a safe HTTP 503. The UI shows a recoverable error. Empty tables show
  a clear no-activity message. Refresh and period selection reload data.
- Backend tests mock the SQL connection. No real Databricks call is made in CI.

## How to verify after deployment

Open `/admin`, sign in, select **Recipe popularity**, change the time
window, and check the bars against read-only SQL aggregation directly in
Databricks. Verify that UTC cutoff is used and that `user_clicks` reflects
both cached and newly generated recipe opens. If SQL warehouse permissions
are missing, fix them in the Databricks workspace, not the frontend.
