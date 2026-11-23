"""Opt-in Ollama recipe generation after the Gemini model pool fails.

No default connection is attempted. A reachable Ollama HTTP API and model must
both be configured on the backend. All output follows the cloud recipe schema.
"""
import asyncio
import logging
import os
from urllib.parse import urlparse

import httpx

from recipe_parsing import parse_recipe_response
from schemas import RecipeSchema

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 20.0
MAX_TIMEOUT = 30.0
MAX_OLLAMA_REPLY_BYTES = 80_000


def ollama_config():
    """Return validated server-owned settings, or None when disabled."""
    base_url = os.getenv("OLLAMA_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "").strip()
    if not base_url or not model:
        return None
    parsed = urlparse(base_url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query or parsed.fragment
        or parsed.path not in ("", "/")
        or len(model) > 120
    ):
        logger.warning("recipe.fallback status=invalid_configuration")
        return None
    try:
        timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT)))
        if not (2 <= timeout <= MAX_TIMEOUT):
            raise ValueError("timeout outside supported range")
    except (ValueError, OverflowError):
        logger.warning("recipe.fallback status=invalid_timeout")
        timeout = DEFAULT_TIMEOUT
    return base_url, model, timeout


async def generate_ollama_recipe(state, *, config=None):
    """Call Ollama asynchronously and return a validated recipe dict.

    The client must NOT request arbitrary user-provided URLs; configuration is
    read from server-side environment variables only.
    """
    config = config if config is not None else ollama_config()
    if config is None:
        raise RuntimeError("Ollama fallback is not configured")
    base_url, model, timeout = config
    dish = state.selected_dish
    if not dish:
        raise ValueError("Recipe fallback requires a selected dish")
    restrictions = ", ".join(state.dietary_preferences) or "none"
    prompt = (
        f"Write a practical, authentic recipe for {dish!r}, cuisine {state.cuisine!r}. "
        f"Strict dietary restrictions: {restrictions}. Never include ingredients "
        "that violate the restrictions. Return ONLY a valid JSON object containing "
        "these keys: dish_name, prep_time, cook_time, servings, ingredients "
        "(array of strings), instructions (array of actionable strings), "
        "chef_pro_tip. Supply actual usable cooking steps and ingredients. "
        "Do not invent citations or claim a web search was performed."
    )
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            response = await asyncio.wait_for(
                client.post(
                    base_url + "/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "options": {"num_predict": 1600},
                    },
                ),
                timeout=timeout + 1,
            )
            response.raise_for_status()
            if len(response.content) > MAX_OLLAMA_REPLY_BYTES:
                raise ValueError("Ollama response exceeded maximum size")
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Ollama returned a non-object envelope")
        raw = payload.get("response")
        recipe = parse_recipe_response(raw)
        return RecipeSchema.model_validate(recipe).model_dump()
    except (httpx.HTTPError, asyncio.TimeoutError, ValueError, TypeError) as exc:
        logger.warning("recipe.fallback status=failed kind=%s", type(exc).__name__)
        raise RuntimeError("Ollama fallback unavailable or invalid") from exc
