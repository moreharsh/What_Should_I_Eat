"""Lightweight browser-bound username profiles backed by opaque Redis sessions.

A username is a display label, not proof of identity. Every new session receives
a distinct random user ID and token. There is no cross-device login/recovery.
"""
import json
import re
import secrets
from uuid import uuid4

from fastapi import Header, HTTPException

from data_layer import redis_client

SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,24}$")


def create_profile(username: str) -> dict:
    cleaned = username.strip()
    if not USERNAME_PATTERN.fullmatch(cleaned):
        raise ValueError("Username must be 3-24 letters, digits or underscores")
    identity = {"user_id": str(uuid4()), "username": cleaned}
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
        return profile
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc


def revoke_profile(token: str):
    redis_client.delete(f"profile:session:{token}")
