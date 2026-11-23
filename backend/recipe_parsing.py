"""Bounded parsing and schema validation of Gemini recipe output."""
import json

from pydantic import ValidationError

from schemas import RecipeSchema

MAX_RECIPE_RESPONSE_CHARS = 30_000


def parse_recipe_response(text: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Gemini returned no recipe text")
    if len(text) > MAX_RECIPE_RESPONSE_CHARS:
        raise ValueError("Gemini recipe text exceeded the maximum size")

    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            value = "\n".join(lines[1:-1]).strip()

    try:
        document = json.loads(value)
        parsed = RecipeSchema.model_validate(document)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("Gemini recipe response did not match the required schema") from exc

    return parsed.model_dump()
