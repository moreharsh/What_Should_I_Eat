"""Demo-only username profiles with stable Redis identities and revocable sessions.

Username-only login is NOT authentication: anyone who enters a known username
can open that profile. Use a password/passkey provider before storing private data.
"""
import json
import re
import secrets
from uuid import uuid4

from fastapi import Header, HTTPException

from data_layer import redis_client

SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,24}$")


def username_key(username: str) -> str:
    return f"profile:username:v1:{username.casefold()}"


def claim_profile(profile: dict) -> None:
    """Register a still-active legacy profile without replacing an existing owner.

    This can migrate an active PR #17 session before the user signs out.
    Already-revoked sessions cannot be recovered from a username alone.
    """
    redis_client.set(username_key(profile["username"]), json.dumps({
        "user_id": profile["user_id"], "username": profile["username"]
    }), nx=True)


def create_profile(username: str) -> dict:
    cleaned = username.strip()
    if not USERNAME_PATTERN.fullmatch(cleaned):
        raise ValueError("Username must be 3-24 letters, digits or underscores")

    key = username_key(cleaned)
    proposed = {"user_id": str(uuid4()), "username": cleaned}
    # SET NX is atomic; competing first logins cannot allocate two IDs.
    if redis_client.set(key, json.dumps(proposed), nx=True):
        identity = proposed
    else:
        identity = json.loads(redis_client.get(key))
        if not isinstance(identity, dict) or not identity.get("user_id"):
            raise RuntimeError("Invalid stored profile")

    token = secrets.token_urlsafe(32)
    redis_client.setex(
        f"profile:session:{token}", SESSION_TTL_SECONDS, json.dumps(identity)
    )
    return {**identity, "token": token}


def get_profile(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in with a username")
    token = authorization[7:]
    if not token or len(token) > 256:
        raise HTTPException(status_code=401, detail="Invalid session")
    stored = redis_client.get(f"profile:session:{token}")
    if not stored:
        raise HTTPException(status_code=401, detail="Session expired. Sign in again")
    try:
        profile = json.loads(stored)
        if not profile.get("user_id") or not profile.get("username"):
            raise ValueError("Invalid profile")
        claim_profile(profile)
        return profile
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc


def revoke_profile(token: str):
    redis_client.delete(f"profile:session:{token}")
