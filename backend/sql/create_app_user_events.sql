-- Run in the Databricks SQL editor if the runtime service account
-- cannot create Delta tables on its own. Requires CREATE TABLE privileges.
-- This stores profile activity; Redis remains the primary live state.
CREATE TABLE IF NOT EXISTS default.app_user_events (
    user_id STRING,
    username STRING,
    event_type STRING,
    dish_name STRING,
    cuisine STRING,
    dietary_restrictions STRING,
    event_at TIMESTAMP
) USING DELTA;

-- Inspect recent events after deployment:
-- SELECT username, event_type, dish_name, cuisine, event_at
-- FROM default.app_user_events
-- ORDER BY event_at DESC
-- LIMIT 50;
