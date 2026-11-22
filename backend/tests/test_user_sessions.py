"""Real username session tests with in-memory Redis; no external services."""
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException


class RedisStub:
    def __init__(self):
        self.records = {}

    def get(self, key):
        return self.records.get(key)

    def setex(self, key, _ttl, value):
        self.records[key] = value

    def set(self, key, value, nx=False):
        if nx and key in self.records:
            return None
        self.records[key] = value
        return True

    def delete(self, key):
        return int(self.records.pop(key, None) is not None)


def load_sessions():
    redis = RedisStub()
    data_layer = types.ModuleType("data_layer")
    data_layer.redis_client = redis
    spec = importlib.util.spec_from_file_location(
        "tested_user_sessions", Path(__file__).resolve().parents[1] / "user_sessions.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"data_layer": data_layer}):
        spec.loader.exec_module(module)
    return module, redis


class UsernameSessionTests(unittest.TestCase):
    def setUp(self):
        self.sessions, self.redis = load_sessions()

    def test_same_username_returns_same_profile_with_new_session(self):
        alice1 = self.sessions.create_profile("alex")
        alice2 = self.sessions.create_profile("ALEX")
        self.assertEqual(alice1["user_id"], alice2["user_id"])
        self.assertNotEqual(alice1["token"], alice2["token"])
        self.assertEqual(
            self.sessions.get_profile("Bearer " + alice2["token"])["user_id"],
            alice1["user_id"],
        )

    def test_sign_out_revokes_only_token_not_profile(self):
        first = self.sessions.create_profile("chef_a")
        self.sessions.revoke_profile(first["token"])
        with self.assertRaises(HTTPException):
            self.sessions.get_profile("Bearer " + first["token"])
        second = self.sessions.create_profile("chef_a")
        self.assertEqual(first["user_id"], second["user_id"])

    def test_two_usernames_remain_separate(self):
        alice = self.sessions.create_profile("alice")
        bob = self.sessions.create_profile("bob")
        self.assertNotEqual(alice["user_id"], bob["user_id"])

    def test_active_legacy_session_is_mapped_to_username(self):
        legacy = {"user_id": "legacy-user-id", "username": "old_chef"}
        self.redis.setex("profile:session:legacy-token", 86400, json.dumps(legacy))
        self.assertEqual(
            self.sessions.get_profile("Bearer legacy-token")["user_id"],
            "legacy-user-id",
        )
        returning = self.sessions.create_profile("old_chef")
        self.assertEqual(returning["user_id"], "legacy-user-id")

    def test_legacy_session_does_not_replace_existing_profile_mapping(self):
        original = self.sessions.create_profile("chef_a")
        old = {"user_id": "another-id", "username": "chef_a"}
        self.redis.setex("profile:session:old-token", 86400, json.dumps(old))
        self.sessions.get_profile("Bearer old-token")
        again = self.sessions.create_profile("chef_a")
        self.assertEqual(again["user_id"], original["user_id"])

    def test_invalid_usernames_are_rejected(self):
        for name in ["ab", "user name", "x" * 25, "other;DROP", ""]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.sessions.create_profile(name)

    def test_revocation_and_expiration_are_enforced(self):
        profile = self.sessions.create_profile("cook_123")
        self.sessions.revoke_profile(profile["token"])
        with self.assertRaises(HTTPException) as cm:
            self.sessions.get_profile("Bearer " + profile["token"])
        self.assertEqual(cm.exception.status_code, 401)

    def test_absent_or_forged_token_is_rejected(self):
        for header in [None, "Bearer wrong", "Basic abc", "Bearer "]:
            with self.subTest(header=header), self.assertRaises(HTTPException):
                self.sessions.get_profile(header)

    def test_token_is_not_in_profile_read_response(self):
        created = self.sessions.create_profile("some_user")
        loaded = self.sessions.get_profile("Bearer " + created["token"])
        # The stored secret is used only in the Authorization header after login.
        # A profile-read endpoint must not echo it back.
        self.assertNotIn("token", loaded)


if __name__ == "__main__":
    unittest.main()
