# Analytics dashboard quality and filtering (Issue #31)

The authenticated `/admin` dashboard exposes recipe popularity, daily activity, and engagement. The three views use one shared 7/30/90-day selector.

## Time window and metrics

All three use **N UTC calendar dates including today**, with explicit Databricks session timezone `UTC`. The lower bound is midnight UTC on the earliest date; the exclusive upper bound is midnight UTC tomorrow. The final day is partial. Changing the selector makes all three tabs use the same date range when visited; do not add raw click counts to profile event counts because they are different instrumentation streams.

The optional daily-activity event filter selects one of six event types already delivered in the bounded aggregate result; it does not change the backend date window or request another warehouse scan. Popularity aggregates retain fixed top-ten bounds. Daily activity has up to 540 date/event buckets; engagement has five aggregate action rows.

## Quality and freshness

An authenticated `GET /api/admin/analytics-quality?days=7|30|90` returns aggregate-only metadata for the existing `default.app_user_events` and `default.user_clicks` tables. It exposes:

- Event-row count from the six recorded profile event types.
- Click-row count and tracked recipe-open count (within `CachedCuisine` and `DiscoveryFeed`).
- Latest profile-event and recipe-click timestamps in UTC, if any.
- Profile event rows with missing or non-UUID user IDs, including historical `harsh_123` rows. These remain included in event totals but are excluded from distinct UUID-profile counts.

Counts are **observed telemetry**, not unique people, proof of cooking, session retention, or proof that no activity occurred. Event logging is best effort. Historical or missing instrumentation cannot be inferred from zeros. There is no automated backfill or migration in this change.

If an entire reporting window has no logged records, counts are zero and latest timestamps are null. An unavailable/misconfigured warehouse produces HTTP 503 instead of a synthetic zero. If the quality query alone fails, previously successful analytics charts remain visible and the freshness section shows a separate warning. No private identifiers, tokens, raw events or SQL are returned by the quality endpoint.

## Performance, accessibility, and verification

The browser reuses per-window quality metadata for five minutes, while an explicit Refresh bypasses it. Tab/window switches abort obsolete requests and discard late responses. A logout clears cached metadata. This reduces extra quality scans but does not prevent the first two bounded aggregate queries for a new timeframe.

Popularity charts include structured data tables; Daily Activity and Engagement already include readable data tables, event labels, and counts. Charts use visible text counts and explanatory labels rather than color alone. Tab navigation and filters use native keyboard controls. Verify layouts at mobile, tablet and desktop sizes.

After deployment: compare SQL results for 7/30/90-day UTC windows, confirm the latest event timestamps, check missing/legacy UUID counts, test rapid window/tab switches and the Refresh action, check keyboard navigation and horizontal table scrolling, and test zero-event versus unavailable warehouse responses. No credentials or schema changes are needed.
