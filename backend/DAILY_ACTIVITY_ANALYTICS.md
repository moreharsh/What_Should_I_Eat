# Daily profile activity trends (Issue #29)

Admin-only dashboard: `/admin` → **Daily activity**.

## Source and event definitions

Read-only, server-aggregated reporting uses the existing `default.app_user_events` Delta table:
`profile_created`, `viewed`, `saved`, `unsaved`, `tried`, and `untried`.

- **Event count**: number of logged event rows for that type and UTC date. A profile can produce multiple events, and every one counts. This is not a count of unique users.
- **Daily distinct profile UUIDs**: distinct valid UUID-form `user_id` values for that date and event type, after normalizing case. This is an estimate of distinct profiles *seen in telemetry*, not verified humans and not a period-wide distinct-user total. Legacy or malformed non-UUID IDs do not contribute to the distinct count, though their events still count.
- This is not a click funnel. Recipe-open clicks live in `default.user_clicks` and are **not** included. The six event types are separate action categories.
- Logging is best-effort; missing historical events cannot be reconstructed.

## Time and zero buckets

The reporting session sets `TIME ZONE 'UTC'` explicitly. `days=7|30|90` means **today in UTC plus N-1 previous complete calendar dates**, not a trailing N×24-hour interval. Today is partial. The date range is inclusive of 00:00 UTC on the first day and exclusive of 00:00 UTC tomorrow.

Databricks generates all N calendar dates and all six event types, left joins grouped counts, and reports **zero for dates with no rows**. It returns exactly 6×N records. An inaccessible/misconfigured warehouse, missing table or malformed results return **HTTP 503**, not synthetic zeroes.

## API and privacy

`GET /api/admin/activity-trends?days=30` requires the same authenticated Redis-backed admin bearer session as other admin endpoints. Only a fixed allowlisted SQL query is executed; allowed windows are 7, 30, and 90. Other values return HTTP 422. No raw event rows, usernames, UUIDs, tokens, or secrets leave the backend. Response rows contain only:

```json
{"date":"2026-11-24","event_type":"viewed","count":4,"distinct_profiles":2}
```

Metadata identifies the UTC timezone and each count's semantics. For 90 days the maximum is 540 aggregate buckets.

## How to verify after deployment

1. Sign into `/admin` and select **Daily activity**.
2. Check each time window (7, 30, 90) and each event type; verify charts and the accessible daily data table agree.
3. Validate the counts in Databricks using UTC session timezone and a fixed calendar-day range. A single UUID logging four `viewed` events on one day must count as four events and one daily distinct profile.
4. Check missing-event dates are visible as zero and that an unavailable warehouse produces a visible error instead of zero.
5. No schema migrations, new credentials, or Redis keys are required.
