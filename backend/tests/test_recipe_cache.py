"""Regression tests for Issue #2. Run: cd backend && python -m unittest discover -s tests -v"""
import json
import unittest

from recipe_cache import normalize_dietary_restrictions, recipe_cache_key, user_history_key


class RecipeCacheTests(unittest.TestCase):
    def test_restrictions_are_sorted_case_insensitive_and_unique(self):
        self.assertEqual(
            normalize_dietary_restrictions([" Vegan ", "GLUTEN_free", "vegan"]),
            ["gluten-free", "vegan"],
        )

    def test_same_variant_is_stable_across_order_and_case(self):
        first = recipe_cache_key(" Dal Makhani ", "Indian", ["Vegan", "Gluten-Free"])
        second = recipe_cache_key("dal   makhani", "INDIAN", ["gluten-free", "vegan", "VEGAN"])
        self.assertEqual(first, second)

    def test_restricted_and_unrestricted_are_distinct(self):
        ordinary = recipe_cache_key("Pasta", "Italian", [])
        dairy_free = recipe_cache_key("Pasta", "Italian", ["Dairy-Free"])
        vegan = recipe_cache_key("Pasta", "Italian", ["Vegan"])
        self.assertEqual(len({ordinary, dairy_free, vegan}), 3)

    def test_cuisines_do_not_share_recipe_entries(self):
        self.assertNotEqual(
            recipe_cache_key("Curry", "Indian", ["Vegetarian"]),
            recipe_cache_key("Curry", "Thai", ["Vegetarian"]),
        )

    def test_v2_keys_cannot_equal_legacy_dish_only_keys(self):
        key = recipe_cache_key("Masala Dosa", "Indian", [])
        self.assertTrue(key.startswith("recipe:v2:"))
        self.assertNotEqual(key, "recipe:masala_dosa")

    def test_history_namespace_is_versioned_and_per_user(self):
        self.assertEqual(user_history_key("alice"), "user:alice:cooked:v2")
        self.assertNotEqual(user_history_key("alice"), user_history_key("bob"))


if __name__ == "__main__":
    unittest.main()
