"""Canonical, versioned keys for dietary-specific recipe variants.

Never read the previous recipe:{dish} keys for restricted requests: those
entries did not record dietary requirements and cannot be trusted.
"""
import hashlib
import json
import re


def normalize_dietary_restrictions(restrictions=None):
    return sorted({r.strip().casefold().replace("_", "-") for r in (restrictions or []) if r.strip()})


def recipe_cache_key(dish_name, cuisine, restrictions=None):
    identity = {
        "dish": " ".join(dish_name.split()).casefold(),
        "cuisine": " ".join(cuisine.split()).casefold(),
        "dietary_restrictions": normalize_dietary_restrictions(restrictions),
    }
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return f"recipe:v2:{digest}"


def user_history_key(user_id):
    return f"user:{user_id}:cooked:v2"


def user_saved_key(user_id):
    return f"user:{user_id}:saved:v2"


def user_viewed_key(user_id):
    return f"user:{user_id}:viewed:v2"
