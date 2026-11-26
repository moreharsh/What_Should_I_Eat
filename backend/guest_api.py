"""One-click, isolated guest session API.

A fixed display name never acts as a shared account or identity. Limits are
applied by hashed client address before issuing an anonymous bearer session.
"""
import hashlib
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from data_layer import redis_client, log_profile_event_to_databricks
from user_sessions import create_guest_profile

router = APIRouter(tags=["guest"])
logger = logging.getLogger(__name__)

# Bounded anonymous session creation to limit automated demo abuse.
GUEST_CREATIONS_PER_15_MIN = 10
GUEST_WINDOW_SECONDS = 15 * 60


@router.post("/api/guest-session")
def start_guest_session(request: Request, background_tasks: BackgroundTasks):
    # The source address is used only for throttling; never return/log it.
    client_address = request.client.host if request.client else "unknown"
    digest = hashlib.sha256(client_address.encode("utf-8")).hexdigest()
    key = "guest:attempts:v1:" + digest
    try:
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, GUEST_WINDOW_SECONDS)
        if count > GUEST_CREATIONS_PER_15_MIN:
            raise HTTPException(status_code=429, detail="Too many guest sessions. Try again later.")
        profile = create_guest_profile()
    except HTTPException:
        raise
    except Exception:
        logger.warning("Guest session creation temporarily unavailable")
        raise HTTPException(status_code=503, detail="Guest access temporarily unavailable") from None

    background_tasks.add_task(
        log_profile_event_to_databricks, profile["user_id"],
        profile["username"], "profile_created",
    )
    return profile
