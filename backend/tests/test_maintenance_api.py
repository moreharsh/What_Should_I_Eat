"""Isolated coverage for the authenticated Redis maintenance heartbeat."""
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.fail = False

    def set(self, key, value):
        if self.fail:
            raise ConnectionError("mock Redis unreachable")
        self.values[key] = value

    def get(self, key):
        if self.fail:
            raise ConnectionError("mock Redis unreachable")
        return self.values.get(key)


def make_app():
    redis = FakeRedis()
    fake_data_layer = types.ModuleType("data_layer")
    fake_data_layer.redis_client = redis
    spec = importlib.util.spec_from_file_location(
        "maintenance_api_under_test",
        Path(__file__).resolve().parents[1] / "maintenance_api.py",
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"data_layer": fake_data_layer}):
        spec.loader.exec_module(module)
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app), redis, module


class HeartbeatTests(unittest.TestCase):
    def setUp(self):
        self.client, self.redis, self.module = make_app()
        self.token = "test-heartbeat-token-" + "x" * 32
        self.env = patch.dict(os.environ, {"REDIS_HEARTBEAT_TOKEN": self.token})
        self.env.start()
        self.addCleanup(self.env.stop)

    def auth(self):
        return {"X-Heartbeat-Token": self.token}

    def test_missing_or_incorrect_token_cannot_read_or_write(self):
        for method in (self.client.get, self.client.post):
            self.assertEqual(method("/api/maintenance/redis-heartbeat").status_code, 401)
            self.assertEqual(method(
                "/api/maintenance/redis-heartbeat",
                headers={"X-Heartbeat-Token": "incorrect"}
            ).status_code, 401)
        self.assertEqual(self.redis.values, {})

    def test_unconfigured_or_short_secret_fails_closed(self):
        for secret in ("", "short"):
            with patch.dict(os.environ, {"REDIS_HEARTBEAT_TOKEN": secret}):
                self.assertEqual(self.client.post(
                    "/api/maintenance/redis-heartbeat", headers=self.auth()
                ).status_code, 401)
        self.assertEqual(self.redis.values, {})

    def test_post_updates_timestamp_and_get_reads_without_rewriting(self):
        url = "/api/maintenance/redis-heartbeat"
        first = self.client.post(url, headers=self.auth())
        self.assertEqual(first.status_code, 200)
        timestamp = first.json()["last_updated_utc"]
        self.assertIn("+00:00", timestamp)
        self.assertEqual(self.redis.values[self.module.HEARTBEAT_KEY], timestamp)
        current = self.client.get(url, headers=self.auth())
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json()["last_updated_utc"], timestamp)
        self.assertEqual(len(self.redis.values), 1)

    def test_read_before_first_write_returns_null(self):
        result = self.client.get("/api/maintenance/redis-heartbeat", headers=self.auth())
        self.assertEqual(result.status_code, 200)
        self.assertIsNone(result.json()["last_updated_utc"])

    def test_connection_failure_returns_safe_503(self):
        self.redis.fail = True
        for method in (self.client.get, self.client.post):
            result = method("/api/maintenance/redis-heartbeat", headers=self.auth())
            self.assertEqual(result.status_code, 503)
            self.assertNotIn("mock Redis unreachable", result.text)


if __name__ == "__main__":
    unittest.main()
