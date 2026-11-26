"""Isolated one-click guest API tests with an in-memory Redis fake."""
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


class RedisFake:
    def __init__(self):
        self.values = {}
        self.expiry = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, seconds, value):
        self.values[key] = value
        self.expiry[key] = seconds

    def incr(self, key):
        count = int(self.values.get(key, 0)) + 1
        self.values[key] = str(count)
        return count

    def expire(self, key, seconds):
        self.expiry[key] = seconds

    def delete(self, key):
        return int(self.values.pop(key, None) is not None)


def build_guest_app():
    redis = RedisFake()
    data = types.ModuleType("data_layer")
    data.redis_client = redis
    data.log_profile_event_to_databricks = AsyncMock()
    root = Path(__file__).resolve().parents[1]
    session_spec = importlib.util.spec_from_file_location(
        "guest_test_user_sessions", root / "user_sessions.py",
    )
    sessions = importlib.util.module_from_spec(session_spec)
    with patch.dict(sys.modules, {"data_layer": data}):
        session_spec.loader.exec_module(sessions)
    guest_spec = importlib.util.spec_from_file_location(
        "guest_test_api", root / "guest_api.py",
    )
    guest = importlib.util.module_from_spec(guest_spec)
    with patch.dict(sys.modules, {
        "data_layer": data, "user_sessions": sessions,
    }):
        guest_spec.loader.exec_module(guest)
    app = FastAPI()
    app.include_router(guest.router)

    from fastapi import Depends, Header

    @app.get("/api/session")
    def session(profile=Depends(sessions.get_profile)):
        return profile

    @app.delete("/api/session")
    def logout(authorization: str = Header(default=""), profile=Depends(sessions.get_profile)):
        sessions.revoke_profile(authorization.removeprefix("Bearer "))
        return {"ok": True}

    return TestClient(app), redis, sessions, guest, data


class GuestSessionTests(unittest.TestCase):
    def setUp(self):
        self.client, self.redis, self.sessions, self.guest, self.data = build_guest_app()

    def test_guest_no_credentials_and_distinct_identities(self):
        first = self.client.post("/api/guest-session", json={})
        second = self.client.post("/api/guest-session", json={})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        a, b = first.json(), second.json()
        self.assertEqual(a["username"], "Guest User")
        self.assertEqual(b["username"], "Guest User")
        self.assertEqual(a["account_type"], "guest")
        self.assertNotEqual(a["user_id"], b["user_id"])
        self.assertNotEqual(a["token"], b["token"])
        self.assertNotIn("password", first.text)
        self.assertEqual(
            self.client.get("/api/session", headers={
                "Authorization": "Bearer " + a["token"],
            }).json()["user_id"], a["user_id"],
        )
        self.assertEqual(
            self.client.get("/api/session", headers={
                "Authorization": "Bearer " + b["token"],
            }).json()["user_id"], b["user_id"],
        )
        self.assertFalse(any(a["token"] in key for key in self.redis.values))
        self.assertEqual(self.data.log_profile_event_to_databricks.await_count, 2)

    def test_guest_exit_and_new_session_cannot_recover_old_history(self):
        a = self.client.post("/api/guest-session").json()
        headers = {"Authorization": "Bearer " + a["token"]}
        self.assertEqual(self.client.get("/api/session", headers=headers).status_code, 200)
        self.assertEqual(self.client.delete("/api/session", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/session", headers=headers).status_code, 401)
        b = self.client.post("/api/guest-session").json()
        self.assertNotEqual(a["user_id"], b["user_id"])

    def test_guest_creation_limited_and_bad_request_body_has_no_identity_input(self):
        self.assertEqual(
            self.client.post("/api/guest-session", json={"user_id": "target-id"}).status_code,
            200,
        )
        # No user-supplied ID can be used; server always makes a UUID.
        result = self.client.post("/api/guest-session", json={"username": "someone"})
        self.assertNotEqual(result.json()["user_id"], "target-id")
        for _ in range(self.guest.GUEST_CREATIONS_PER_15_MIN - 2):
            self.assertEqual(self.client.post("/api/guest-session").status_code, 200)
        self.assertEqual(self.client.post("/api/guest-session").status_code, 429)
        self.assertTrue(any(k.startswith("guest:attempts:v1:") for k in self.redis.values))

    def test_guest_model_budget_only_applies_to_guest_user(self):
        profile = self.client.post("/api/guest-session").json()
        for _ in range(20):
            self.guest.limit_guest_generation(profile, "recipe")
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as error:
            self.guest.limit_guest_generation(profile, "recipe")
        self.assertEqual(error.exception.status_code, 429)
        self.assertIn(
            f"guest:usage:v1:{profile['user_id']}:recipe", self.redis.values,
        )
        self.guest.limit_guest_generation({
            "account_type": "registered", "username": "chef", "user_id": "registered",
        }, "recipe")
        self.assertFalse(any("registered:recipe" in k for k in self.redis.values))

    def test_unavailable_redis_fails_without_fake_success(self):
        def fail(*_args, **_kwargs):
            raise RuntimeError("connection secrets never returned")
        self.redis.incr = fail
        response = self.client.post("/api/guest-session")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("connection secrets", response.text)


if __name__ == "__main__":
    unittest.main()
