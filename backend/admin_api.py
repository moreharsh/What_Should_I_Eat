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
