# Recipe engagement analytics — Issue #30

Admin-only read-only dashboard: `/admin` → **Recipe engagement**.

## Data and exact metric contract

All measures are derived solely from logged rows in `default.app_user_events` for events `viewed`, `saved`, `unsaved`, `tried`, and `untried`. These are **action events**, not reconstructed current Redis state, unique recipe views, unique users, or evidence of real-world cooking.

| Measure | Numerator | Denominator or comparison | Interpretation |
| --- | --- | --- | --- |
| Viewed event volume | Number of `viewed` rows | None | Repeated views count repeatedly |
| Saved event volume | Number of `saved` rows | None | Records save actions, including repeated actions in history |
| Tried event volume | Number of `tried` rows | None | Records marking a recipe as tried; does not verify cooking |
| Unsaved/untried volume | Count of corresponding undo rows | None | Each undo is a separate action |
| Distinct profile UUIDs per action | Distinct well-formed UUID `user_id` values for one event type in the window | None | Counts profiles with that action, not distinct people or recipe counts |
| Save-to-view action ratio | Saved event count × 100 | Viewed event count | Action-volume ratio; **not a conversion rate** and may exceed 100% |
| Tried-to-view action ratio | Tried event count × 100 | Viewed event count | Action-volume ratio; **not a conversion rate** and may exceed 100% |
| Net save actions | Saved event count − unsaved event count | Difference, not a rate | Signed event balance, **not** current saved recipe count |
| Net tried actions | Tried event count − untried event count | Difference, not a rate | Signed event balance, **not** current tried recipe count |

When the viewed-event denominator is zero, each action ratio is `null` and displayed as N/A, never 0%. Valid profile UUIDs are case-normalized for distinct counting; missing or malformed identifiers do not increase distinct-profile counts, but their logged action rows still count in event volume. Distinct counts for different action types cannot be added together to count unique profiles.

## Window, completeness and limitations

The SQL session explicitly sets `TIME ZONE 'UTC'`. Supported windows are 7, 30, and 90 **UTC calendar dates including today** (the current day is partial). The lower bound is midnight UTC on the earliest date; upper bound is midnight UTC tomorrow. This matches Issue #29 Daily Activity, not the rolling-hour time cutoff of Issue #28.

Repeated actions are counted as separate events. A saved event followed by unsaved counts in both action categories and contributes zero net save actions. A missing undo event can skew net totals. Events logged before instrumentation, missing best-effort telemetry, older data without `user_id` in UUID format, incomplete migration, and deleted/expired profile state **cannot be reconstructed**. A small observed sample does not imply reliable conversion or retention. UI labels avoid attributing actual cooking or continued activity to the person.

## API, security and failure states

`GET /api/admin/engagement?days=30` requires an authenticated, short-lived admin bearer session. Only fixed allowlisted SQL is used, with 7/30/90-day parameter validation (HTTP 422 otherwise). The SQL runs aggregates server-side and returns exactly five rows (`event_type`, `count`, `distinct_profiles`) plus derived summary values. The response has no per-user records, usernames, raw UUIDs, recipe details, or credentials.

For a configured but inaccessible/failed warehouse, the API returns a safe HTTP 503 and the UI shows an error. A successful query with no rows yields five zero-count aggregates and N/A action ratios. No new secrets, Redis keys, migrations or Databricks tables are needed.

## Production verification

1. Sign in to `/admin`, select **Recipe engagement**, and switch through the 7/30/90-day windows.
2. Compare the five action counts and per-type distinct profile counts with a read-only Databricks `GROUP BY event_type` query using the same UTC boundaries.
3. Check the two action ratios against saved/viewed and tried/viewed counts; verify N/A when there are zero views, and negative signed net values where undo actions exceed adds.
4. Test the accessible charts and data table using keyboard navigation and screen reader headings.
5. Verify a warehouse failure displays an error rather than appearing as zero engagement.
