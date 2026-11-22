"""Tests for conservative ingredient screening; not allergen certification."""
import unittest

from dietary_validation import incompatible_ingredients


class DietaryValidationTests(unittest.TestCase):
    def test_rejects_meat_in_vegetarian_recipe(self):
        self.assertEqual(
            incompatible_ingredients({"ingredients": ["200 g chicken breast", "tomatoes"]}, ["vegetarian"]),
            ["200 g chicken breast"],
        )

    def test_rejects_dairy_or_eggs_in_vegan_recipe(self):
        self.assertEqual(
            incompatible_ingredients({"ingredients": ["2 eggs", "1 cup milk", "rice"]}, ["vegan"]),
            ["2 eggs", "1 cup milk"],
        )

    def test_allows_explicit_plant_milk(self):
        self.assertEqual(
            incompatible_ingredients({"ingredients": ["coconut milk", "oat milk", "rice"]}, ["vegan", "dairy-free"]),
            [],
        )

    def test_gluten_free_blocks_explicit_wheat(self):
        self.assertEqual(
            incompatible_ingredients({"ingredients": ["wheat flour", "tomato"]}, ["gluten-free"]),
            ["wheat flour"],
        )

    def test_unknown_restriction_is_rejected(self):
        with self.assertRaises(ValueError):
            incompatible_ingredients({"ingredients": ["rice"]}, ["unknown-diet"])

    def test_bad_ingredients_structure_is_rejected(self):
        with self.assertRaises(ValueError):
            incompatible_ingredients({"ingredients": "rice"}, ["vegan"])


if __name__ == "__main__":
    unittest.main()
