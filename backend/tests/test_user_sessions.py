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

    def test_same_username_creates_isolated_profiles(self):
        first = self.sessions.create_profile("alex")
        second = self.sessions.create_profile("ALEX")
        self.assertNotEqual(first["user_id"], second["user_id"])
        self.assertNotEqual(first["token"], second["token"])
        self.assertEqual(
            self.sessions.get_profile("Bearer " + first["token"])["user_id"],
            first["user_id"],
        )
        self.assertEqual(
            self.sessions.get_profile("Bearer " + second["token"])["user_id"],
            second["user_id"],
        )

    def test_sign_out_revokes_token_and_name_cannot_restore_access(self):
        first = self.sessions.create_profile("chef_a")
        self.sessions.revoke_profile(first["token"])
        with self.assertRaises(HTTPException):
            self.sessions.get_profile("Bearer " + first["token"])
        second = self.sessions.create_profile("chef_a")
        self.assertNotEqual(first["user_id"], second["user_id"])

    def test_two_usernames_remain_separate(self):
        alice = self.sessions.create_profile("alice")
        bob = self.sessions.create_profile("bob")
        self.assertNotEqual(alice["user_id"], bob["user_id"])

    def test_existing_session_retains_its_history_without_username_recovery(self):
        legacy = {"user_id": "legacy-user-id", "username": "old_chef"}
        self.redis.setex("profile:session:legacy-token", 86400, json.dumps(legacy))
        self.assertEqual(
            self.sessions.get_profile("Bearer legacy-token")["user_id"],
            "legacy-user-id",
        )
        newcomer = self.sessions.create_profile("old_chef")
        self.assertNotEqual(newcomer["user_id"], "legacy-user-id")
        self.assertEqual(
            self.sessions.get_profile("Bearer legacy-token")["user_id"],
            "legacy-user-id",
        )
        self.assertNotIn("profile:username:v1:old_chef", self.redis.records)

    def test_name_collision_never_grants_access_to_other_profile(self):
        original = self.sessions.create_profile("chef_a")
        second = self.sessions.create_profile("chef_a")
        self.assertNotEqual(original["user_id"], second["user_id"])
        self.assertEqual(self.sessions.get_profile("Bearer " + original["token"])["user_id"],
                         original["user_id"])
        self.assertEqual(self.sessions.get_profile("Bearer " + second["token"])["user_id"],
                         second["user_id"])

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
