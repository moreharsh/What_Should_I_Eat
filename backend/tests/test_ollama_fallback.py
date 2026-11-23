"""Cloud-first recipe fallback tests. No live LLM or Ollama service needed."""
import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from ollama_fallback import generate_ollama_recipe, ollama_config
from recipe_workflow import build_recipe_graph
from schemas import AgentState


def sample_recipe():
    return {
        "dish_name": "Tomato Pasta",
        "prep_time": "10 minutes",
        "cook_time": "20 minutes",
        "servings": "2",
        "ingredients": ["pasta", "tomato", "olive oil"],
        "instructions": ["Boil pasta.", "Simmer tomato sauce.", "Combine and serve."],
        "chef_pro_tip": "Add fresh basil.",
    }


def state():
    return AgentState(
        selected_dish="Tomato Pasta", cuisine="Italian", dietary_preferences=["vegan"],
    )


async def media(_state):
    return {"media_links": {"image_url": "example"}}


class OllamaFallbackGraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_gemini_success_never_calls_ollama(self):
        calls = []

        def chef(_state):
            calls.append("gemini")
            return {"recipe_details": sample_recipe()}

        with patch("recipe_workflow.ollama_config", return_value=("http://local", "test", 2)), \
             patch("recipe_workflow.generate_ollama_recipe", new_callable=AsyncMock) as local:
            result = await build_recipe_graph(chef, media).ainvoke(state())
            self.assertEqual(result["recipe_details"]["dish_name"], "Tomato Pasta")
            self.assertEqual(calls, ["gemini"])
            local.assert_not_awaited()

    async def test_gemini_failure_with_local_success(self):
        def chef(_state):
            raise RuntimeError("Gemini service down")

        with patch("recipe_workflow.ollama_config", return_value=("http://local", "test", 2)), \
             patch("recipe_workflow.generate_ollama_recipe", new_callable=AsyncMock, return_value=sample_recipe()) as local:
            result = await build_recipe_graph(chef, media).ainvoke(state())
            self.assertEqual(result["recipe_details"]["dish_name"], "Tomato Pasta")
            local.assert_awaited_once()

    async def test_local_failure_becomes_controlled_recipe_error(self):
        def chef(_state):
            raise RuntimeError("Gemini service down")

        with patch("recipe_workflow.ollama_config", return_value=("http://local", "test", 2)), \
             patch("recipe_workflow.generate_ollama_recipe", new_callable=AsyncMock, side_effect=RuntimeError("offline")):
            with self.assertRaisesRegex(RuntimeError, "All configured recipe providers failed"):
                await build_recipe_graph(chef, media).ainvoke(state())

    async def test_unconfigured_local_preserves_cloud_failure(self):
        def chef(_state):
            raise RuntimeError("Gemini service down")

        with patch("recipe_workflow.ollama_config", return_value=None), \
             patch("recipe_workflow.generate_ollama_recipe", new_callable=AsyncMock) as local:
            with self.assertRaisesRegex(RuntimeError, "Gemini service down"):
                await build_recipe_graph(chef, media).ainvoke(state())
            local.assert_not_awaited()

    async def test_invalid_cloud_recipe_triggers_local(self):
        def chef(_state):
            return {"recipe_details": {"dish_name": "fake recipe"}}

        with patch("recipe_workflow.ollama_config", return_value=("http://local", "test", 2)), \
             patch("recipe_workflow.generate_ollama_recipe", new_callable=AsyncMock, return_value=sample_recipe()):
            result = await build_recipe_graph(chef, media).ainvoke(state())
            self.assertEqual(result["recipe_details"]["instructions"][0], "Boil pasta.")

    async def test_local_request_uses_validated_response(self):
        envelope = {"response": json.dumps(sample_recipe())}
        fake = MagicMock()
        fake.status_code = 200
        fake.content = json.dumps(envelope).encode("utf-8")
        fake.json.return_value = envelope
        fake.raise_for_status.return_value = None
        session = AsyncMock()
        session.post.return_value = fake
        context = AsyncMock()
        context.__aenter__.return_value = session
        with patch("ollama_fallback.httpx.AsyncClient", return_value=context):
            result = await generate_ollama_recipe(state(), config=("http://localhost:11434", "test-model", 5))
        self.assertEqual(result["dish_name"], "Tomato Pasta")
        self.assertEqual(session.post.call_args.args[0], "http://localhost:11434/api/generate")
        self.assertFalse(session.post.call_args.kwargs["json"]["stream"])

    async def test_invalid_ollama_json_or_steps_are_rejected(self):
        for value in ["not json", json.dumps({**sample_recipe(), "instructions": []})]:
            with self.subTest(value=value):
                envelope = {"response": value}
                fake = MagicMock()
                fake.content = json.dumps(envelope).encode("utf-8")
                fake.json.return_value = envelope
                fake.raise_for_status.return_value = None
                session = AsyncMock()
                session.post.return_value = fake
                context = AsyncMock()
                context.__aenter__.return_value = session
                with patch("ollama_fallback.httpx.AsyncClient", return_value=context):
                    with self.assertRaisesRegex(RuntimeError, "Ollama fallback unavailable or invalid"):
                        await generate_ollama_recipe(state(), config=("http://localhost:11434", "test", 5))

    async def test_ollama_http_timeout_is_bounded(self):
        session = AsyncMock()
        session.post.side_effect = httpx.TimeoutException("timed out")
        context = AsyncMock()
        context.__aenter__.return_value = session
        with patch("ollama_fallback.httpx.AsyncClient", return_value=context):
            with self.assertRaisesRegex(RuntimeError, "Ollama fallback unavailable"):
                await generate_ollama_recipe(state(), config=("http://localhost:11434", "test", 2))

    async def test_async_fallback_allows_other_requests_to_run(self):
        async def slow_recipe(_state):
            await asyncio.sleep(0.02)
            return sample_recipe()

        def chef(_state):
            raise RuntimeError("Gemini down")

        with patch("recipe_workflow.ollama_config", return_value=("http://local", "test", 2)), \
             patch("recipe_workflow.generate_ollama_recipe", side_effect=slow_recipe):
            task = asyncio.create_task(build_recipe_graph(chef, media).ainvoke(state()))
            event_loop_progressed = False
            await asyncio.sleep(0.005)
            event_loop_progressed = not task.done()
            await task
            self.assertTrue(event_loop_progressed)


class OllamaConfigTests(unittest.TestCase):
    def test_disabled_by_default_and_rejects_incomplete_settings(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(ollama_config())
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://localhost:11434"}, clear=True):
            self.assertIsNone(ollama_config())

    def test_requires_configured_safe_base_url_and_caps_timeouts(self):
        values = {"OLLAMA_BASE_URL": "http://localhost:11434", "OLLAMA_MODEL": "qwen2.5:7b"}
        with patch.dict(os.environ, values, clear=True):
            self.assertEqual(ollama_config(), ("http://localhost:11434", "qwen2.5:7b", 20.0))
        with patch.dict(os.environ, {**values, "OLLAMA_TIMEOUT_SECONDS": "999"}, clear=True):
            self.assertEqual(ollama_config()[2], 20.0)
        with patch.dict(os.environ, {**values, "OLLAMA_BASE_URL": "file:///etc/passwd"}, clear=True):
            self.assertIsNone(ollama_config())


if __name__ == "__main__":
    unittest.main()
