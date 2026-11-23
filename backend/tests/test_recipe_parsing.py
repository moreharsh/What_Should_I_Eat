"""Tests for recipe JSON validation and safe rejection of invalid AI output."""
import json
import unittest

from recipe_parsing import parse_recipe_response

VALID_RECIPE = {
    "dish_name": "Pasta",
    "prep_time": "10 minutes",
    "cook_time": "20 minutes",
    "servings": "2",
    "ingredients": ["Pasta", "Tomato"],
    "instructions": ["Boil water.", "Cook pasta."],
    "chef_pro_tip": "Taste before serving.",
}


class RecipeParsingTests(unittest.TestCase):
    def test_plain_and_fenced_json(self):
        value = json.dumps(VALID_RECIPE)
        self.assertEqual(parse_recipe_response(value)["dish_name"], "Pasta")
        self.assertEqual(
            parse_recipe_response("```json\n" + value + "\n```")["dish_name"],
            "Pasta",
        )

    def test_malformed_and_missing_fields(self):
        for value in ["", "{bad json", json.dumps({"dish_name": "Pasta"})]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_recipe_response(value)

    def test_empty_or_oversized_instructions_are_rejected(self):
        for instructions in [[], ["   "], ["x" * 1001]]:
            with self.subTest(instructions=instructions), self.assertRaises(ValueError):
                parse_recipe_response(json.dumps({
                    **VALID_RECIPE, "instructions": instructions,
                }))

    def test_bounded_length_and_blank_strings(self):
        with self.assertRaises(ValueError):
            parse_recipe_response(json.dumps({**VALID_RECIPE, "dish_name": "  "}))
        with self.assertRaises(ValueError):
            parse_recipe_response("x" * 30_001)


if __name__ == "__main__":
    unittest.main()
