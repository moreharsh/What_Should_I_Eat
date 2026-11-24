"""Authenticated, deliberately small Redis activity heartbeat for evaluation databases.

This is operational maintenance, not user activity or application health.
No arbitrary Redis keys, values, database connections, or commands are exposed.
"""

import logging
import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException

from data_layer import redis_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])

HEARTBEAT_KEY = "maintenance:redis-heartbeat:last-updated-utc"


def _require_heartbeat_token(provided: str | None) -> None:
    expected = os.getenv("REDIS_HEARTBEAT_TOKEN", "")
    # Fail closed when maintenance access has not been deliberately configured.
    if len(expected) < 32 or not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/redis-heartbeat")
def write_redis_heartbeat(x_heartbeat_token: str | None = Header(default=None)):
    """Write the UTC timestamp on each authorized invocation.

    Sync route lets FastAPI run the blocking redis-py client in a threadpool.
    """
    _require_heartbeat_token(x_heartbeat_token)
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        redis_client.set(HEARTBEAT_KEY, timestamp)
    except Exception:
        logger.warning("Redis maintenance heartbeat failed")
        raise HTTPException(status_code=503, detail="Redis heartbeat unavailable") from None

    return {"status": "ok", "last_updated_utc": timestamp}


@router.get("/redis-heartbeat")
def read_redis_heartbeat(x_heartbeat_token: str | None = Header(default=None)):
    """Read the most recent heartbeat for operators without changing its timestamp."""
    _require_heartbeat_token(x_heartbeat_token)
    try:
        timestamp = redis_client.get(HEARTBEAT_KEY)
    except Exception:
        logger.warning("Redis maintenance heartbeat status unavailable")
        raise HTTPException(status_code=503, detail="Redis heartbeat unavailable") from None

    return {"status": "ok", "last_updated_utc": timestamp}
