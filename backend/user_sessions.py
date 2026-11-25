"""Isolated anonymous recipe profiles, identified by unguessable bearer sessions.

Usernames are display names only: knowing one never grants access to another
profile. Returning visitors must keep their existing device session token.
This is not password or cross-device account authentication.
"""
import json
import re
import secrets
from uuid import uuid4

from fastapi import Header, HTTPException

from data_layer import redis_client

SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
PROFILE_REGISTRY_TTL_SECONDS = 90 * 24 * 60 * 60
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,24}$")


def create_profile(username: str) -> dict:
    cleaned = username.strip()
    if not USERNAME_PATTERN.fullmatch(cleaned):
        raise ValueError("Username must be 3-24 letters, digits or underscores")
    # Always generate a fresh identity; never resolve username -> existing ID.
    # Different browsers using the same display name must remain isolated.
    identity = {"user_id": str(uuid4()), "username": cleaned}
    token = secrets.token_urlsafe(32)
    redis_client.setex(
        f"profile:session:{token}", SESSION_TTL_SECONDS, json.dumps(identity)
    )
    # Admin-only listing index. This key is never consulted for authentication.
    redis_client.setex(
        f"profile:registry:v2:{identity['user_id']}",
        PROFILE_REGISTRY_TTL_SECONDS, json.dumps(identity),
    )
    return {**identity, "token": token}


def get_profile(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Start a recipe session")
    token = authorization[7:]
    if not token or len(token) > 256:
        raise HTTPException(status_code=401, detail="Invalid session")
    stored = redis_client.get(f"profile:session:{token}")
    if not stored:
        raise HTTPException(status_code=401, detail="Session expired. Start a new profile")
    try:
        profile = json.loads(stored)
        if not isinstance(profile, dict):
            raise ValueError("Invalid profile")
        # Existing session tokens issued before this change stay valid until
        # their TTL. They retain their original history, without enabling
        # username-based recovery or creating any new claimable identity.
        if not isinstance(profile.get("username"), str) or not profile["username"]:
            raise ValueError("Invalid profile")
        user_id = profile.get("user_id")
        if not isinstance(user_id, str) or not user_id or len(user_id) > 128:
            raise ValueError("Invalid profile")
        return {"user_id": user_id, "username": profile["username"]}
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc


def revoke_profile(token: str):
    redis_client.delete(f"profile:session:{token}")
