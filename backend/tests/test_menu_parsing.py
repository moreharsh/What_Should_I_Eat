"""Regression tests for Gemini menu JSON parsing."""
import unittest

from menu_parsing import parse_menu_response


VALID = '{"options":[{"dish_name":"Tacos","teaser":"Easy dinner","primary_protein":"Beans"}]}'


class MenuParsingTests(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(parse_menu_response(VALID)[0]["dish_name"], "Tacos")

    def test_fenced_json(self):
        self.assertEqual(parse_menu_response("```json\n" + VALID + "\n```")[0]["dish_name"], "Tacos")

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


if __name__ == "__main__":
    unittest.main()
