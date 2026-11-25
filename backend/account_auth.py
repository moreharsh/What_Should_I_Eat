"""Persistent Redis accounts with Argon2id, recovery codes, and revocable sessions.

Account creation is atomic via a fixed Redis Lua script; usernames never confer
access to guest history. Anonymous-to-account upgrades require a live bearer token.
"""
import hashlib
import json
import re
import secrets
from uuid import UUID, uuid4

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from data_layer import redis_client
from user_sessions import get_profile, revoke_profile, SESSION_TTL_SECONDS

router = APIRouter(prefix="/api/auth", tags=["account"])
hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, type=Type.ID)
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,24}$")
RATE_LIMIT_SECONDS = 15 * 60
REGISTER_SCRIPT = """
-- Atomic uniqueness on both username and UUID, including upgrades.
if redis.call('EXISTS', KEYS[1]) == 1 or
   redis.call('EXISTS', KEYS[2]) == 1 or
   redis.call('EXISTS', KEYS[3]) == 1 then return 0 end
redis.call('SET', KEYS[1], ARGV[1])
redis.call('SET', KEYS[2], ARGV[2])
redis.call('SET', KEYS[3], ARGV[1])
return 1
"""


class AccountCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=24)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("username")
    @classmethod
    def username_valid(cls, value):
        if not USERNAME_PATTERN.fullmatch(value):
            raise ValueError("Username must have 3–24 letters, numbers or underscores")
        return value


class RecoverCredentials(AccountCredentials):
    recovery_code: str = Field(min_length=32, max_length=128)


def _username_key(username):
    return "account:username:v1:" + username.casefold()


def _account_key(user_id):
    return "account:user:v1:" + user_id


def _owner_key(user_id):
    return "account:owner:v1:" + user_id


def _rate_limit(request, operation, username, limit=10):
    # Never store the IP address or submitted username in readable Redis keys.
    source = (request.client.host if request.client else "unknown")
    fingerprint = hashlib.sha256(f"{operation}|{source}|{username.casefold()}".encode()).hexdigest()
    key = "account:attempts:v1:" + fingerprint
    attempts = redis_client.incr(key)
    if attempts == 1:
        redis_client.expire(key, RATE_LIMIT_SECONDS)
    if attempts > limit:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    # A second IP-only bound prevents rotating usernames to avoid throttling.
    broad_key = "account:attempts:v1:" + hashlib.sha256(
        f"{operation}|{source}".encode()
    ).hexdigest()
    broad_attempts = redis_client.incr(broad_key)
    if broad_attempts == 1:
        redis_client.expire(broad_key, RATE_LIMIT_SECONDS)
    if broad_attempts > (20 if operation == "register" else 60):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")


def _new_recovery_code():
    # Single-use high-entropy recovery code. Shown only at signup/reset.
    return secrets.token_urlsafe(32)


def _code_hash(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _session(identity):
    token = secrets.token_urlsafe(36)
    key = "profile:session:v2:" + hashlib.sha256(token.encode("utf-8")).hexdigest()
    epoch = int(redis_client.get("account:epoch:v1:" + identity["user_id"]) or 0)
    redis_client.setex(key, SESSION_TTL_SECONDS, json.dumps({**identity, "epoch": epoch}))
    return {**identity, "token": token}


def _load_account(username):
    user_id = redis_client.get(_username_key(username))
    if not user_id:
        return None
    try:
        account = json.loads(redis_client.get(_account_key(user_id)) or "{}")
    except (ValueError, TypeError):
        return None
    if account.get("user_id") != user_id or account.get("username", "").casefold() != username.casefold():
        return None
    return account


@router.post("/register")
def register(body: AccountCredentials, request: Request, authorization: str = Header(default="")):
    _rate_limit(request, "register", body.username, 5)
    old_token = ""
    user_id = str(uuid4())
    if authorization:
        # A live bearer token is necessary to claim existing anonymous history.
        profile = get_profile(authorization)
        if profile.get("account_type") == "registered":
            raise HTTPException(status_code=409, detail="Already registered")
        user_id = profile["user_id"]
        try:
            UUID(user_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=409, detail="Legacy profile cannot be upgraded") from None
        # Old shared pre-#49 IDs are unsafe to claim, even with a valid token.
        legacy_key = "profile:username:v1:" + profile["username"].casefold()
        legacy = redis_client.get(legacy_key)
        if legacy:
            try:
                if json.loads(legacy).get("user_id") == user_id:
                    raise HTTPException(status_code=409, detail="Shared legacy profile cannot be upgraded")
            except (ValueError, TypeError):
                raise HTTPException(status_code=409, detail="Legacy profile cannot be upgraded") from None
        old_token = authorization.removeprefix("Bearer ")
    account = {
        "user_id": user_id, "username": body.username,
        "password_hash": hasher.hash(body.password),
    }
    recovery_code = _new_recovery_code()
    account["recovery_hash"] = _code_hash(recovery_code)
    created = redis_client.eval(
        REGISTER_SCRIPT, 3, _username_key(body.username),
        _account_key(user_id), _owner_key(user_id),
        user_id, json.dumps(account),
    )
    if created != 1:
        raise HTTPException(status_code=409, detail="Username unavailable or profile already registered")
    identity = {"user_id": user_id, "username": body.username, "account_type": "registered"}
    redis_client.setex("profile:registry:v2:" + user_id, 90 * 86400, json.dumps(identity))
    result = _session(identity)
    if old_token:
        revoke_profile(old_token)
    return {**result, "recovery_code": recovery_code}


@router.post("/login")
def login(body: AccountCredentials, request: Request):
    _rate_limit(request, "login", body.username)
    account = _load_account(body.username)
    if account is None:
        # Perform a dummy Argon2 verification to reduce account enumeration.
        try:
            hasher.verify(DUMMY_HASH, body.password)
        except (VerifyMismatchError, VerificationError):
            pass
        raise HTTPException(status_code=401, detail="Invalid username or password")
    try:
        if not hasher.verify(account["password_hash"], body.password):
            raise VerifyMismatchError()
    except (VerifyMismatchError, VerificationError, KeyError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid username or password") from None
    identity = {"user_id": account["user_id"], "username": account["username"],
                "account_type": "registered"}
    redis_client.setex("profile:registry:v2:" + account["user_id"],
                       90 * 86400, json.dumps(identity))
    return _session(identity)


@router.post("/recover")
def recover(body: RecoverCredentials, request: Request):
    _rate_limit(request, "recover", body.username, 5)
    account = _load_account(body.username)
    if account is None or not secrets.compare_digest(
        account.get("recovery_hash", ""), _code_hash(body.recovery_code)
    ):
        raise HTTPException(status_code=401, detail="Invalid recovery credentials")
    # Recovery code rotation must be atomic: racing replays may not both succeed.
    next_code = _new_recovery_code()
    updated = {**account, "password_hash": hasher.hash(body.password),
               "recovery_hash": _code_hash(next_code)}
    key = _account_key(account["user_id"])
    script = """
    if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
    redis.call('SET', KEYS[1], ARGV[2])
    return 1
    """
    if redis_client.eval(script, 1, key, json.dumps(account), json.dumps(updated)) != 1:
        raise HTTPException(status_code=409, detail="Recovery code already used; try again")
    # Incrementing the generation invalidates all previously issued account
    # bearer sessions without scanning tokens or exposing their Redis keys.
    redis_client.incr("account:epoch:v1:" + account["user_id"])
    return {"ok": True, "recovery_code": next_code}


@router.get("/me")
def me(profile=Depends(get_profile)):
    return profile


@router.post("/logout")
def logout(authorization: str = Header(default=""), profile=Depends(get_profile)):
    revoke_profile(authorization.removeprefix("Bearer "))
    return {"ok": True}


# Precomputed from a fixed local dummy password; never a live user secret.
DUMMY_HASH = hasher.hash("not-a-real-user-password")
