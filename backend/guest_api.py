"""One-click, isolated guest session API.

A fixed display name never acts as a shared account or identity. Limits are
applied by hashed client address before issuing an anonymous bearer session.
"""
import hashlib
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from data_layer import redis_client, log_profile_event_to_databricks
from user_sessions import create_guest_profile

router = APIRouter(tags=["guest"])
logger = logging.getLogger(__name__)

# Bounded anonymous session creation to limit automated demo abuse.
GUEST_CREATIONS_PER_15_MIN = 10
GUEST_WINDOW_SECONDS = 15 * 60


class EmptyGuestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.post("/api/guest-session")
def start_guest_session(
    request: Request, background_tasks: BackgroundTasks,
    _body: EmptyGuestRequest | None = None,
):
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


def limit_guest_generation(profile: dict, operation: str):
    """Bound daily paid-model calls for Guest User without shared account IDs.

    This is intentionally an additional per-session budget rather than a
    substitute for global API abuse controls or reverse-proxy rate limits.
    """
    if profile.get("account_type") != "guest" or profile.get("username") != "Guest User":
        return
    allowed = {"menu": 40, "recipe": 20}
    if operation not in allowed:
        raise ValueError("Unknown guest operation")
    key = f"guest:usage:v1:{profile['user_id']}:{operation}"
    try:
        calls = redis_client.incr(key)
        if calls == 1:
            redis_client.expire(key, 24 * 60 * 60)
        if calls > allowed[operation]:
            raise HTTPException(
                status_code=429,
                detail="Guest demo limit reached. Try again tomorrow or create an account.",
            )
    except HTTPException:
        raise
    except Exception:
        logger.warning("Guest usage limit unavailable")
        raise HTTPException(status_code=503, detail="Guest access temporarily unavailable") from None
