"""Mocked Redis account security tests: no network, Gemini or warehouse."""
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


class RedisFake:
    def __init__(self):
        self.values = {}
        self.expiry = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.expiry[key] = ttl

    def incr(self, key):
        n = int(self.values.get(key, 0)) + 1
        self.values[key] = str(n)
        return n

    def expire(self, key, ttl):
        self.expiry[key] = ttl

    def delete(self, key):
        return int(self.values.pop(key, None) is not None)

    def eval(self, script, nkeys, *args):
        keys, values = args[:nkeys], args[nkeys:]
        if nkeys == 3:
            if any(key in self.values for key in keys):
                return 0
            self.values[keys[0]] = values[0]
            self.values[keys[1]] = values[1]
            self.values[keys[2]] = values[0]
            return 1
        if nkeys == 1:
            if self.values.get(keys[0]) != values[0]:
                return 0
            self.values[keys[0]] = values[1]
            return 1
        raise ValueError("Unexpected Redis script")


def build_app():
    redis = RedisFake()
    data_layer = types.ModuleType("data_layer")
    data_layer.redis_client = redis
    root = Path(__file__).resolve().parents[1]
    spec_session = importlib.util.spec_from_file_location(
        "user_sessions", root / "user_sessions.py",
    )
    sessions = importlib.util.module_from_spec(spec_session)
    with patch.dict(sys.modules, {"data_layer": data_layer, "user_sessions": sessions}):
        spec_session.loader.exec_module(sessions)
        spec_auth = importlib.util.spec_from_file_location("account_auth", root / "account_auth.py")
        auth = importlib.util.module_from_spec(spec_auth)
        spec_auth.loader.exec_module(auth)
    app = FastAPI()
    app.include_router(auth.router)
    app.get("/private")(lambda profile=auth.Depends(sessions.get_profile): profile)
    return redis, sessions, TestClient(app)


class PersistentAccountTests(unittest.TestCase):
    def setUp(self):
        self.redis, self.sessions, self.client = build_app()

    def register(self, username="test_chef", password="a-long-secure-password", token=None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.post("/api/auth/register", json={
            "username": username, "password": password,
        }, headers=headers)

    def login(self, username="test_chef", password="a-long-secure-password"):
        return self.client.post("/api/auth/login", json={
            "username": username, "password": password,
        })

    def test_login_after_logout_restores_stable_uuid(self):
        first = self.register().json()
        self.assertIn("recovery_code", first)
        self.assertNotIn(first["password_hash"] if "password_hash" in first else "argon2-hash", first.values())
        uid = first["user_id"]
        self.assertTrue(any("$argon2id$" in str(v) for k, v in self.redis.values.items()
                            if k.startswith("account:user:v1:")))
        original = self.client.get("/private", headers={
            "Authorization": "Bearer " + first["token"],
        })
        self.assertEqual(original.status_code, 200)
        self.assertEqual(original.json()["user_id"], uid)
        self.assertEqual(self.client.post("/api/auth/logout", headers={
            "Authorization": "Bearer " + first["token"],
        }).status_code, 200)
        self.assertEqual(self.client.get("/private", headers={
            "Authorization": "Bearer " + first["token"],
        }).status_code, 401)
        second = self.login()
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["user_id"], uid)
        self.assertNotEqual(second.json()["token"], first["token"])

    def test_username_collision_wrong_password_and_distinct_accounts(self):
        alice = self.register().json()
        self.assertEqual(self.register().status_code, 409)
        self.assertEqual(self.login(password="wrong-password-value").status_code, 401)
        self.assertEqual(self.login(username="not_found").status_code, 401)
        bob = self.register("other_chef").json()
        self.assertNotEqual(alice["user_id"], bob["user_id"])
        self.assertEqual(self.client.get("/private", headers={
            "Authorization": "Bearer " + bob["token"],
        }).json()["user_id"], bob["user_id"])
        self.assertEqual(self.client.get("/private", headers={
            "Authorization": "Bearer forged",
        }).status_code, 401)

    def test_guest_upgrade_preserves_uuid_and_does_not_claim_by_name(self):
        guest = self.sessions.create_profile("demo_chef")
        original_uuid = guest["user_id"]
        upgraded = self.register("permanent_chef", token=guest["token"])
        self.assertEqual(upgraded.status_code, 200, upgraded.text)
        self.assertEqual(upgraded.json()["user_id"], original_uuid)
        self.assertEqual(self.client.get("/private", headers={
            "Authorization": "Bearer " + guest["token"],
        }).status_code, 401)
        self.assertEqual(self.login("permanent_chef").json()["user_id"], original_uuid)
        other_guest = self.sessions.create_profile("demo_chef")
        self.assertNotEqual(other_guest["user_id"], original_uuid)
        self.assertEqual(self.register("another_account", token=other_guest["token"]).status_code, 200)

    def test_shared_legacy_profile_cannot_be_claimed(self):
        guest = self.sessions.create_profile("legacy_name")
        self.redis.values["profile:username:v1:legacy_name"] = json.dumps({
            "username": "legacy_name", "user_id": guest["user_id"],
        })
        result = self.register("new_secure_name", token=guest["token"])
        self.assertEqual(result.status_code, 409)
        self.assertFalse(any(k.startswith("account:username:") for k in self.redis.values))

    def test_one_time_recovery_rotates_code_and_revokes_sessions(self):
        first = self.register().json()
        recovered = self.client.post("/api/auth/recover", json={
            "username": "test_chef", "password": "new-long-password-123",
            "recovery_code": first["recovery_code"],
        })
        self.assertEqual(recovered.status_code, 200, recovered.text)
        self.assertNotEqual(recovered.json()["recovery_code"], first["recovery_code"])
        self.assertEqual(self.client.post("/api/auth/recover", json={
            "username": "test_chef", "password": "different-long-password",
            "recovery_code": first["recovery_code"],
        }).status_code, 401)
        self.assertEqual(self.client.get("/private", headers={
            "Authorization": "Bearer " + first["token"],
        }).status_code, 401)
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.login(password="new-long-password-123").status_code, 200)

    def test_rate_limit_and_password_policy(self):
        for _ in range(5):
            self.assertEqual(self.login(username="nobody").status_code, 401)
        self.assertEqual(self.register(password="short").status_code, 422)
        for _ in range(5):
            self.register(username="many_attempts")
        self.assertEqual(self.register(username="many_attempts").status_code, 429)


if __name__ == "__main__":
    unittest.main()
