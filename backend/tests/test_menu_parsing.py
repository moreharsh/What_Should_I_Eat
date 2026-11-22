"""Regression tests for bounded, distinct Gemini menu JSON parsing."""
import json
import unittest

from menu_parsing import parse_menu_response


OPTIONS = [
    {"dish_name": name, "teaser": "Easy dinner", "primary_protein": "Beans"}
    for name in ("Tacos", "Burritos", "Enchiladas", "Quesadillas", "Tamales")
]
VALID = json.dumps({"options": OPTIONS})


class MenuParsingTests(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(len(parse_menu_response(VALID)), 5)

    def test_fenced_json(self):
        self.assertEqual(len(parse_menu_response("```json\n" + VALID + "\n```")), 5)

    def test_empty_response(self):
        with self.assertRaises(ValueError):
            parse_menu_response("")

    def test_malformed_response(self):
        with self.assertRaises(ValueError):
            parse_menu_response('{"options": [')

    def test_mismatched_schema(self):
        with self.assertRaises(ValueError):
            parse_menu_response('{"options": [{"dish_name": "Tacos"}]}')

    def test_empty_menu(self):
        with self.assertRaises(ValueError):
            parse_menu_response('{"options": []}')

    def test_rejects_fewer_than_five_options(self):
        with self.assertRaises(ValueError):
            parse_menu_response(json.dumps({"options": OPTIONS[:4]}))

    def test_rejects_duplicate_names_case_insensitive(self):
        duplicates = [*OPTIONS[:4], {**OPTIONS[4], "dish_name": " tacos "}]
        with self.assertRaises(ValueError):
            parse_menu_response(json.dumps({"options": duplicates}))

    def test_rejects_blank_or_oversized_fields(self):
        invalid = [*OPTIONS[:4], {**OPTIONS[4], "dish_name": "   "}]
        with self.assertRaises(ValueError):
            parse_menu_response(json.dumps({"options": invalid}))
        with self.assertRaises(ValueError):
            parse_menu_response(" " * 20_001)


if __name__ == "__main__":
    unittest.main()
