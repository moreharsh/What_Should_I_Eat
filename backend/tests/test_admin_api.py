"""Admin endpoints are read-only and unavailable without separate authentication."""
import importlib.util
import json
import os
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
        self.sets = {}
        self.ttls = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.ttls[key] = ttl

    def delete(self, key):
        return int(self.values.pop(key, None) is not None)

    def incr(self, key):
        value = int(self.values.get(key, 0)) + 1
        self.values[key] = str(value)
        return value

    def expire(self, key, seconds):
        self.ttls[key] = seconds

    def smembers(self, key):
        return self.sets.get(key, set())

    def scard(self, key):
        return len(self.smembers(key))

    def type(self, key):
        return "set" if key in self.sets else "string"

    def strlen(self, key):
        return len(self.values.get(key, ""))

    def ttl(self, key):
        return self.ttls.get(key, -1)

    def scan_iter(self, match, count=100):
        prefix = match.rstrip("*")
        for key in sorted(set(self.values) | set(self.sets)):
            if key.startswith(prefix):
                yield key


def create_app():
    redis = RedisFake()
    data_layer = types.ModuleType("data_layer")
    data_layer.redis_client = redis
    data_layer.DB_HOST = None
    data_layer.DB_PATH = None
    data_layer.DB_TOKEN = None
    maintenance = types.ModuleType("maintenance_api")
    maintenance.HEARTBEAT_KEY = "maintenance:redis-heartbeat:last-updated-utc"
    cache = types.ModuleType("recipe_cache")
    cache.user_viewed_key = lambda uid: f"user:{uid}:viewed:v2"
    cache.user_saved_key = lambda uid: f"user:{uid}:saved:v2"
    cache.user_history_key = lambda uid: f"user:{uid}:cooked:v2"
    spec = importlib.util.spec_from_file_location(
        "admin_api_under_test", Path(__file__).resolve().parents[1] / "admin_api.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"data_layer": data_layer, "recipe_cache": cache,
                                  "maintenance_api": maintenance}):
        spec.loader.exec_module(module)
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app), redis


class AdminAPITests(unittest.TestCase):
    def setUp(self):
        self.client, self.redis = create_app()
        self.env = patch.dict(os.environ, {"ADMIN_PASSWORD": "random-password-very-long-123"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def login(self):
        response = self.client.post("/api/admin/login", json={
            "username": "admin", "password": "random-password-very-long-123",
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["token"]

    def test_admin_endpoints_all_require_authentication(self):
        for path in ("/api/admin/users", "/api/admin/redis",
                     "/api/admin/databricks?table=events", "/api/admin/session",
                     "/api/admin/redis-heartbeat"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 401)

    def test_wrong_password_and_fail_closed_configuration(self):
        wrong = self.client.post("/api/admin/login", json={
            "username": "admin", "password": "incorrect",
        })
        self.assertEqual(wrong.status_code, 401)
        with patch.dict(os.environ, {"ADMIN_PASSWORD": "short"}):
            response = self.client.post("/api/admin/login", json={
                "username": "admin", "password": "short",
            })
        self.assertEqual(response.status_code, 503)

    def test_limited_failed_login_attempts(self):
        for _ in range(10):
            self.client.post("/api/admin/login", json={
                "username": "admin", "password": "wrong",
            })
        blocked = self.client.post("/api/admin/login", json={
            "username": "admin", "password": "random-password-very-long-123",
        })
        self.assertEqual(blocked.status_code, 429)

    def test_admin_token_is_revocable_and_hashed_in_redis(self):
        token = self.login()
        self.assertFalse(any(token in key for key in self.redis.values))
        headers = {"Authorization": f"Bearer {token}"}
        self.assertTrue(self.client.get("/api/admin/session", headers=headers).json()["read_only"])
        self.assertEqual(self.client.post("/api/admin/logout", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/admin/users", headers=headers).status_code, 401)

    def test_users_include_viewed_saved_tried_without_session_tokens(self):
        token = self.login()
        uid = "user-123"
        self.redis.values["profile:username:v1:harsh"] = json.dumps({
            "user_id": uid, "username": "Harsh",
        })
        self.redis.values["recipe:v2:abc"] = json.dumps({
            "dish_name": "Dal", "cuisine": "indian", "dietary_restrictions": ["vegan"],
        })
        for suffix in ("viewed", "saved", "cooked"):
            self.redis.sets[f"user:{uid}:{suffix}:v2"] = {"recipe:v2:abc"}
        self.redis.values["profile:session:private-session-token"] = "private"
        response = self.client.get("/api/admin/users", headers={
            "Authorization": f"Bearer {token}",
        })
        self.assertEqual(response.status_code, 200, response.text)
        user = response.json()["users"][0]
        self.assertEqual(user["username"], "Harsh")
        self.assertEqual(user["counts"], {"viewed": 1, "saved": 1, "tried": 1})
        self.assertEqual(user["viewed"][0]["dish_name"], "Dal")
        self.assertNotIn("private-session-token", response.text)

    def test_redis_inspector_hides_auth_keys_and_values(self):
        token = self.login()
        self.redis.values["recipe:v2:abc"] = '{"secret_recipe_body":"not returned"}'
        self.redis.values["profile:session:private-token"] = "secret"
        response = self.client.get("/api/admin/redis", headers={
            "Authorization": f"Bearer {token}",
        })
        self.assertEqual(response.status_code, 200)
        text = response.text
        self.assertIn("recipe:v2:abc", text)
        self.assertNotIn("private-token", text)
        self.assertNotIn("secret_recipe_body", text)
        self.assertNotIn("admin:session:", text)

    def test_redis_heartbeat_is_read_only_and_separate_from_general_inspector(self):
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        key = "maintenance:redis-heartbeat:last-updated-utc"
        url = "/api/admin/redis-heartbeat"

        missing = self.client.get(url, headers=headers)
        self.assertEqual(missing.status_code, 200)
        self.assertEqual(missing.json(), {"key": key, "last_updated_utc": None})

        timestamp = "2026-11-24T01:26:57.386045+00:00"
        self.redis.values[key] = timestamp
        original = dict(self.redis.values)
        response = self.client.get(url, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"key": key, "last_updated_utc": timestamp})
        self.assertEqual(self.redis.values, original)

        inspector = self.client.get("/api/admin/redis", headers=headers)
        self.assertEqual(inspector.status_code, 200)
        self.assertNotIn(key, inspector.text)
        self.assertNotIn(timestamp, inspector.text)

    def test_redis_heartbeat_status_unavailable_returns_safe_error(self):
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        with patch.object(self.redis, "get", side_effect=ConnectionError("private Redis URI")):
            response = self.client.get("/api/admin/redis-heartbeat", headers=headers)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private Redis URI", response.text)

    def test_databricks_table_is_allowlisted_and_absent_service_safe(self):
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(self.client.get(
            "/api/admin/databricks?table=default.app_user_events;DELETE",
            headers=headers,
        ).status_code, 422)
        response = self.client.get("/api/admin/databricks?table=events", headers=headers)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("traceback", response.text.lower())


if __name__ == "__main__":
    unittest.main()
