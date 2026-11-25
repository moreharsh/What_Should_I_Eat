"""Read-only administrative API for recipe analytics.

All administrative routes require a separate password and a short-lived,
opaque, Redis-backed admin session. Never expose provider credentials, raw
tokens, unrestricted Redis commands, or arbitrary SQL to the client.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

import data_layer
from data_layer import redis_client
from recipe_cache import user_history_key, user_saved_key, user_viewed_key
from maintenance_api import HEARTBEAT_KEY

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])
ADMIN_SESSION_TTL = 8 * 60 * 60
MAX_PROFILES = 100
MAX_REDIS_KEYS = 100
MAX_EVENTS = 75
ADMIN_USERNAME = "admin"
SAFE_KEY_PREFIXES = ("profile:username:v1:", "user:", "recipe:v2:")
USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


class AdminCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=512)


def _admin_session_key(token: str) -> str:
    return "admin:session:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def _configured_password() -> str:
    # Fail closed rather than silently enabling a default admin account.
    password = os.getenv("ADMIN_PASSWORD", "")
    if len(password) < 16:
        raise HTTPException(status_code=503, detail="Admin access is not configured")
    return password


def require_admin(authorization: str | None = Header(default=None)) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Admin authentication required")
    token = authorization.removeprefix("Bearer ")
    if not 32 <= len(token) <= 256:
        raise HTTPException(status_code=401, detail="Invalid admin session")
    if not redis_client.get(_admin_session_key(token)):
        raise HTTPException(status_code=401, detail="Admin session expired")
    return True


@router.post("/login")
def login(request: Request, credentials: AdminCredentials):
    password = _configured_password()
    # Fixed-size attempt window; never include usernames/passwords in Redis.
    client = request.client.host if request.client else "unknown"
    key = "admin:attempts:" + hashlib.sha256(client.encode("utf-8")).hexdigest()
    attempts = redis_client.incr(key)
    if attempts == 1:
        redis_client.expire(key, 15 * 60)
    if attempts > 10:
        raise HTTPException(status_code=429, detail="Too many attempts; retry later")
    matched = (
        hmac.compare_digest(credentials.username, ADMIN_USERNAME)
        and hmac.compare_digest(credentials.password, password)
    )
    if not matched:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    redis_client.delete(key)
    token = secrets.token_urlsafe(36)
    redis_client.setex(_admin_session_key(token), ADMIN_SESSION_TTL, "admin")
    return {"token": token, "expires_in": ADMIN_SESSION_TTL}


@router.get("/session")
def session(admin=Depends(require_admin)):
    return {"authenticated": True, "role": "admin", "read_only": True}


@router.post("/logout")
def logout(authorization: str = Header(default=""), admin=Depends(require_admin)):
    redis_client.delete(_admin_session_key(authorization.removeprefix("Bearer ")))
    return {"ok": True}


def _visible_recipe_keys(user_id: str, label: str, limit: int = 30):
    if label == "viewed":
        key = user_viewed_key(user_id)
    elif label == "saved":
        key = user_saved_key(user_id)
    else:
        key = user_history_key(user_id)
    output = []
    for cache_key in sorted(redis_client.smembers(key))[:limit]:
        # Never return raw keys/contents that don't match our application format.
        if not cache_key.startswith("recipe:v2:"):
            continue
        raw = redis_client.get(cache_key)
        if not raw:
            continue
        try:
            item = json.loads(raw)
            if not isinstance(item, dict):
                continue
            output.append({
                "dish_name": str(item.get("dish_name", ""))[:120],
                "cuisine": str(item.get("cuisine", ""))[:80],
                "dietary_restrictions": item.get("dietary_restrictions", []),
            })
        except (ValueError, TypeError):
            continue
    return output


@router.get("/users")
def users(admin=Depends(require_admin)):
    records = []
    # Bounded results: SCAN not KEYS, and never enumerate session tokens.
    for key in redis_client.scan_iter(match="profile:username:v1:*", count=100):
        if len(records) >= MAX_PROFILES:
            break
        try:
            identity = json.loads(redis_client.get(key) or "{}")
            user_id = str(identity.get("user_id", ""))
            username = str(identity.get("username", ""))[:64]
            if not USER_ID_PATTERN.fullmatch(user_id) or not username:
                continue
            viewed = _visible_recipe_keys(user_id, "viewed")
            saved = _visible_recipe_keys(user_id, "saved")
            tried = _visible_recipe_keys(user_id, "tried")
            records.append({
                "user_id": user_id,
                "username": username,
                "viewed": viewed,
                "saved": saved,
                "tried": tried,
                "counts": {
                    "viewed": redis_client.scard(user_viewed_key(user_id)),
                    "saved": redis_client.scard(user_saved_key(user_id)),
                    "tried": redis_client.scard(user_history_key(user_id)),
                },
            })
        except (ValueError, TypeError, AttributeError):
            continue
    return {"users": sorted(records, key=lambda user: user["username"].casefold()),
            "limit": MAX_PROFILES, "note": "Recent profile registry only; older orphaned sessions are excluded."}


@router.get("/redis")
def redis_inspection(admin=Depends(require_admin)):
    records = []
    # Only application recipe/profile keys. Never return profile sessions,
    # admin sessions, auth attempts, Redis configuration or unfiltered values.
    for prefix in SAFE_KEY_PREFIXES:
        for key in redis_client.scan_iter(match=prefix + "*", count=100):
            if len(records) >= MAX_REDIS_KEYS:
                break
            if key.startswith(("profile:session:", "admin:")):
                continue
            key_type = redis_client.type(key)
            if key_type == "set":
                size = redis_client.scard(key)
            elif key_type == "string":
                size = redis_client.strlen(key)
            else:
                continue
            records.append({
                "key": key if prefix != "profile:username:v1:" else "profile:username:v1:" + key.split(":")[-1],
                "type": key_type,
                "size": size,
                "ttl_seconds": redis_client.ttl(key),
            })
        if len(records) >= MAX_REDIS_KEYS:
            break
    return {"keys": sorted(records, key=lambda item: item["key"]), "limit": MAX_REDIS_KEYS,
            "note": "Read-only metadata for allowlisted keys. Session keys and raw values are hidden."}


@router.get("/redis-heartbeat")
def redis_heartbeat_status(admin=Depends(require_admin)):
    """Read-only maintenance timestamp, separate from recipe/profile key metadata.

    The admin session is sufficient; never send the maintenance write token
    to the browser or expose arbitrary Redis keys.
    """
    try:
        last_updated = redis_client.get(HEARTBEAT_KEY)
    except Exception:
        logger.warning("Admin Redis heartbeat read unavailable")
        raise HTTPException(status_code=503, detail="Redis heartbeat status unavailable") from None
    return {"key": HEARTBEAT_KEY, "last_updated_utc": last_updated}


ALLOWED_TABLES = {
    "events": (
        "SELECT user_id, username, event_type, dish_name, cuisine, "
        "dietary_restrictions, event_at FROM default.app_user_events "
        "ORDER BY event_at DESC LIMIT 75"
    ),
    "clicks": (
        "SELECT user_id, dish_name, cuisine, tracking_context, timestamp "
        "FROM default.user_clicks ORDER BY timestamp DESC LIMIT 75"
    ),
}


@router.get("/databricks")
async def databricks_events(table: str = "events", admin=Depends(require_admin)):
    if table not in ALLOWED_TABLES:
        raise HTTPException(status_code=422, detail="Unknown analytics table")
    if not all([data_layer.DB_HOST, data_layer.DB_PATH, data_layer.DB_TOKEN]):
        raise HTTPException(status_code=503, detail="Databricks is not configured")

    def read():
        from databricks import sql
        with sql.connect(
            server_hostname=data_layer.DB_HOST, http_path=data_layer.DB_PATH,
            access_token=data_layer.DB_TOKEN
        ) as conn:
            with conn.cursor() as cursor:
                # SQL query is a fixed allowlist, never user-generated.
                cursor.execute(ALLOWED_TABLES[table])
                names = [col[0] for col in cursor.description]
                rows = cursor.fetchmany(MAX_EVENTS)
                return [
                    {name: value.isoformat() if hasattr(value, "isoformat") else value
                     for name, value in zip(names, row)}
                    for row in rows
                ]

    try:
        rows = await asyncio.to_thread(read)
    except Exception:
        logger.exception("Admin read-only Databricks query failed: table=%s", table)
        raise HTTPException(status_code=503, detail="Analytics temporarily unavailable") from None
    return {"table": table, "rows": rows, "limit": MAX_EVENTS}


# Aggregates intentionally expose only category labels + counts. Unlike
# /databricks, they never return usernames, user IDs or event payloads.
ANALYTICS_WINDOWS = (7, 30, 90)
POPULARITY_LIMIT = 10


@router.get("/popularity")
async def recipe_popularity(days: int = 30, admin=Depends(require_admin)):
    """Last N UTC days, measured from the Databricks SQL warehouse clock.

    Dish selections are user_clicks recipe-open rows (cached or generated).
    Cuisine views are app_user_events viewed rows. Counts are event counts,
    not unique users and not saved/tried preferences.
    """
    if days not in ANALYTICS_WINDOWS:
        raise HTTPException(status_code=422, detail="Unsupported analytics window")
    if not all([data_layer.DB_HOST, data_layer.DB_PATH, data_layer.DB_TOKEN]):
        raise HTTPException(status_code=503, detail="Databricks is not configured")

    # days is allowlisted above, never an arbitrary SQL fragment or table name.
    cutoff = f"CURRENT_TIMESTAMP() - INTERVAL {days} DAYS"
    queries = (
        (
            "SELECT dish_name AS label, COUNT(*) AS event_count "
            "FROM default.user_clicks "
            f"WHERE timestamp >= {cutoff} "
            "AND tracking_context IN ('CachedCuisine', 'DiscoveryFeed') "
            "AND dish_name IS NOT NULL AND TRIM(dish_name) <> '' "
            "GROUP BY dish_name ORDER BY event_count DESC, label ASC LIMIT 10"
        ),
        (
            "SELECT cuisine AS label, COUNT(*) AS event_count "
            "FROM default.app_user_events "
            f"WHERE event_at >= {cutoff} AND event_type = 'viewed' "
            "AND cuisine IS NOT NULL AND TRIM(cuisine) <> '' "
            "GROUP BY cuisine ORDER BY event_count DESC, label ASC LIMIT 10"
        ),
    )

    def read():
        from databricks import sql
        with sql.connect(
            server_hostname=data_layer.DB_HOST, http_path=data_layer.DB_PATH,
            access_token=data_layer.DB_TOKEN
        ) as conn:
            result = []
            with conn.cursor() as cursor:
                for statement in queries:
                    cursor.execute(statement)
                    rows = cursor.fetchmany(POPULARITY_LIMIT)
                    result.append([
                        {"label": str(label)[:120], "count": int(count)}
                        for label, count in rows
                    ])
            return result

    try:
        dishes, cuisines = await asyncio.to_thread(read)
    except Exception:
        logger.warning("Admin popularity query unavailable")
        raise HTTPException(status_code=503, detail="Analytics temporarily unavailable") from None
    return {
        "days": days,
        "timezone": "UTC",
        "top_dishes": dishes,
        "top_cuisines": cuisines,
        "dish_metric": "recipe_open_events",
        "cuisine_metric": "recipe_view_events",
        "limit": POPULARITY_LIMIT,
    }


# UTC calendar-day activity trends. Exact 7/30/90 date ranges include today
# and N-1 previous UTC dates; they are distinct from rolling-hour popularity.
ACTIVITY_EVENTS = ("profile_created", "viewed", "saved", "unsaved", "tried", "untried")
UUID_SQL_PATTERN = (
    "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    "[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


@router.get("/activity-trends")
async def daily_activity_trends(days: int = 30, admin=Depends(require_admin)):
    """Return a zero-filled UTC date × event matrix, without identities.

    SQL session timezone is explicitly UTC, not the warehouse default.
    Event counts include repeated actions; distinct UUIDs only count logged
    profile identifiers for each day/event (not verified unique people).
    """
    if days not in ANALYTICS_WINDOWS:
        raise HTTPException(status_code=422, detail="Unsupported analytics window")
    if not all([data_layer.DB_HOST, data_layer.DB_PATH, data_layer.DB_TOKEN]):
        raise HTTPException(status_code=503, detail="Databricks is not configured")

    # Date offsets and event names are server-owned allowlists, never client SQL.
    events_sql = ", ".join(f"'{name}'" for name in ACTIVITY_EVENTS)
    statement = f"""
        WITH calendar AS (
            SELECT explode(sequence(date_sub(current_date(), {days - 1}),
                                   current_date(), interval 1 day)) AS activity_date
        ), event_names AS (
            SELECT explode(array({events_sql})) AS event_type
        ), grouped AS (
            SELECT CAST(event_at AS DATE) AS activity_date,
                   event_type,
                   COUNT(*) AS event_count,
                   COUNT(DISTINCT CASE WHEN user_id RLIKE '{UUID_SQL_PATTERN}'
                                       THEN lower(user_id) ELSE NULL END)
                       AS distinct_profiles
            FROM default.app_user_events
            WHERE event_at >= CAST(date_sub(current_date(), {days - 1}) AS TIMESTAMP)
              AND event_at < CAST(date_add(current_date(), 1) AS TIMESTAMP)
              AND event_type IN ({events_sql})
            GROUP BY CAST(event_at AS DATE), event_type
        )
        SELECT calendar.activity_date, event_names.event_type,
               COALESCE(grouped.event_count, 0) AS event_count,
               COALESCE(grouped.distinct_profiles, 0) AS distinct_profiles
        FROM calendar CROSS JOIN event_names
        LEFT JOIN grouped
          ON calendar.activity_date = grouped.activity_date
         AND event_names.event_type = grouped.event_type
        ORDER BY calendar.activity_date ASC, event_names.event_type ASC
    """

    def read():
        from databricks import sql
        with sql.connect(
            server_hostname=data_layer.DB_HOST, http_path=data_layer.DB_PATH,
            access_token=data_layer.DB_TOKEN
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET TIME ZONE 'UTC'")
                cursor.execute(statement)
                return cursor.fetchmany(days * len(ACTIVITY_EVENTS) + 1)

    try:
        raw_rows = await asyncio.to_thread(read)
        expected = days * len(ACTIVITY_EVENTS)
        if len(raw_rows) != expected:
            raise ValueError("Incomplete daily activity matrix")
        records = []
        seen = set()
        for date_value, event_type, event_count, distinct_profiles in raw_rows:
            date_label = date_value.isoformat() if hasattr(date_value, "isoformat") else str(date_value)
            # Verify the response shape before sending metrics to the browser.
            if (not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_label)
                    or event_type not in ACTIVITY_EVENTS
                    or (date_label, event_type) in seen):
                raise ValueError("Invalid daily activity bucket")
            event_count, distinct_profiles = int(event_count), int(distinct_profiles)
            if not (0 <= distinct_profiles <= event_count):
                raise ValueError("Invalid activity counts")
            seen.add((date_label, event_type))
            records.append({
                "date": date_label, "event_type": event_type,
                "count": event_count, "distinct_profiles": distinct_profiles,
            })
    except Exception:
        logger.warning("Admin daily activity query unavailable")
        raise HTTPException(status_code=503, detail="Analytics temporarily unavailable") from None

    return {
        "days": days, "timezone": "UTC",
        "events": list(ACTIVITY_EVENTS),
        "rows": records,
        "metric": "logged_event_count",
        "distinct_metric": "daily_distinct_profile_uuids",
    }


ENGAGEMENT_EVENTS = ("viewed", "saved", "unsaved", "tried", "untried")


def _engagement_summary(rows):
    """Turn fixed event aggregates into action ratios, never user conversion."""
    counts = {item["event_type"]: item["count"] for item in rows}
    views = counts["viewed"]
    saves = counts["saved"]
    tries = counts["tried"]
    def ratio(numerator):
        # Null is an undefined denominator, not a 0% action rate.
        return round(100 * numerator / views, 2) if views else None

    return {
        "save_to_view_action_percent": ratio(saves),
        "tried_to_view_action_percent": ratio(tries),
        "ratio_denominator_event": "viewed",
        "ratio_denominator_count": views,
        "net_save_actions": saves - counts["unsaved"],
        "net_tried_actions": tries - counts["untried"],
    }


@router.get("/engagement")
async def recipe_engagement(days: int = 30, admin=Depends(require_admin)):
    """UTC calendar-day window with fixed aggregate SELECT and no raw identity.

    Repeated actions are counted. Undo events subtract from net *actions* only;
    neither net actions nor the view denominator is a count of current
    saved/tried recipes, distinct recipe views, cooking, or retained people.
    """
    if days not in ANALYTICS_WINDOWS:
        raise HTTPException(status_code=422, detail="Unsupported analytics window")
    if not all([data_layer.DB_HOST, data_layer.DB_PATH, data_layer.DB_TOKEN]):
        raise HTTPException(status_code=503, detail="Databricks is not configured")

    event_names = ", ".join(f"'{name}'" for name in ENGAGEMENT_EVENTS)
    query = f"""
        SELECT event_type, COUNT(*) AS event_count,
               COUNT(DISTINCT CASE
                   WHEN user_id RLIKE '{UUID_SQL_PATTERN}'
                   THEN lower(user_id) ELSE NULL END) AS distinct_profiles
        FROM default.app_user_events
        WHERE event_at >= CAST(date_sub(current_date(), {days - 1}) AS TIMESTAMP)
          AND event_at < CAST(date_add(current_date(), 1) AS TIMESTAMP)
          AND event_type IN ({event_names})
        GROUP BY event_type
    """

    def read():
        from databricks import sql
        with sql.connect(
            server_hostname=data_layer.DB_HOST, http_path=data_layer.DB_PATH,
            access_token=data_layer.DB_TOKEN,
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET TIME ZONE 'UTC'")
                cursor.execute(query)
                return cursor.fetchmany(len(ENGAGEMENT_EVENTS) + 1)

    try:
        raw = await asyncio.to_thread(read)
        if len(raw) > len(ENGAGEMENT_EVENTS):
            raise ValueError("Too many engagement groups")
        by_event = {}
        for event_type, count, distinct_profiles in raw:
            if event_type not in ENGAGEMENT_EVENTS or event_type in by_event:
                raise ValueError("Invalid engagement event")
            count, distinct_profiles = int(count), int(distinct_profiles)
            if not 0 <= distinct_profiles <= count:
                raise ValueError("Invalid engagement aggregate")
            by_event[event_type] = {
                "event_type": event_type, "count": count,
                "distinct_profiles": distinct_profiles,
            }
        rows = [by_event.get(event, {
            "event_type": event, "count": 0, "distinct_profiles": 0,
        }) for event in ENGAGEMENT_EVENTS]
    except Exception:
        logger.warning("Admin engagement query unavailable")
        raise HTTPException(status_code=503, detail="Analytics temporarily unavailable") from None

    return {
        "days": days,
        "timezone": "UTC",
        "metric": "logged_action_events",
        "distinct_metric": "distinct_profile_uuids_per_action",
        "rows": rows,
        "summary": _engagement_summary(rows),
    }
