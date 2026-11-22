"""Parse and validate Gemini menu responses without trusting free-form output."""
import json

from pydantic import ValidationError

from schemas import MenuSchema


def parse_menu_response(text: str) -> list[dict]:
    """Accept raw JSON or a fenced JSON object, rejecting incomplete menus."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Gemini returned no menu text")

    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            value = "\n".join(lines[1:-1]).strip()

    try:
        document = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("Gemini menu response was not valid JSON") from exc

    try:
        menu = MenuSchema.model_validate(document)
    except ValidationError as exc:
        raise ValueError("Gemini menu response did not match the expected schema") from exc

    if not menu.options:
        raise ValueError("Gemini returned an empty list of dishes")
    return [dish.model_dump() for dish in menu.options]
