"""Exercise real LangGraph START fan-out, concurrency and partial failures."""
import asyncio
import threading
import time
import unittest

from langgraph.graph import END, START, StateGraph

from recipe_workflow import build_recipe_graph
from schemas import AgentState


def recipe():
    return {
        "dish_name": "Pasta",
        "prep_time": "5 minutes",
        "cook_time": "10 minutes",
        "servings": "2",
        "ingredients": ["tomato", "rice"],
        "instructions": ["Cook ingredients."],
        "chef_pro_tip": "Serve warm.",
    }


class RecipeGraphIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_branches_start_concurrently_and_merge_state(self):
        chef_started = threading.Event()
        media_started = threading.Event()
        calls = {"chef": 0, "media": 0}

        def chef(state):
            calls["chef"] += 1
            self.assertEqual(state.selected_dish, "Pasta")
            chef_started.set()
            # If media is sequential, this times out and fails the test.
            if not media_started.wait(timeout=1):
                raise AssertionError("Media branch did not start concurrently")
            return {"recipe_details": recipe()}

        async def media(state):
            calls["media"] += 1
            self.assertEqual(state.dietary_preferences, ["vegan"])
            media_started.set()
            for _ in range(100):
                if chef_started.is_set():
                    break
                await asyncio.sleep(0.005)
            self.assertTrue(chef_started.is_set(), "Chef branch never started")
            return {"media_links": {"image_url": "image", "youtube_embed_url": "video"}}

        graph = build_recipe_graph(chef, media, chef_timeout=2, media_timeout=2)
        result = await graph.ainvoke(AgentState(
            cuisine="Italian", selected_dish="Pasta", dietary_preferences=["vegan"]
        ))
        self.assertEqual(calls, {"chef": 1, "media": 1})
        self.assertEqual(result["recipe_details"]["dish_name"], "Pasta")
        self.assertEqual(result["media_links"]["image_url"], "image")
        self.assertEqual(result["selected_dish"], "Pasta")
        self.assertEqual(result["dietary_preferences"], ["vegan"])

    async def test_media_exception_preserves_recipe(self):
        def chef(_):
            return {"recipe_details": recipe()}

        async def media(_):
            raise RuntimeError("external media API down")

        graph = build_recipe_graph(chef, media)
        result = await graph.ainvoke(AgentState(selected_dish="Pasta"))
        self.assertEqual(result["recipe_details"]["dish_name"], "Pasta")
        self.assertIsNone(result["media_links"])

    async def test_media_timeout_preserves_recipe(self):
        def chef(_):
            return {"recipe_details": recipe()}

        async def media(_):
            await asyncio.sleep(0.1)
            return {"media_links": {"image_url": "too late"}}

        graph = build_recipe_graph(chef, media, media_timeout=0.01)
        result = await graph.ainvoke(AgentState(selected_dish="Pasta"))
        self.assertEqual(result["recipe_details"]["dish_name"], "Pasta")
        self.assertIsNone(result["media_links"])

    async def test_chef_failure_is_not_hidden_by_media_success(self):
        def chef(_):
            raise RuntimeError("Gemini unavailable")

        async def media(_):
            return {"media_links": {"image_url": "image"}}

        graph = build_recipe_graph(chef, media)
        with self.assertRaisesRegex(RuntimeError, "Gemini unavailable"):
            await graph.ainvoke(AgentState(selected_dish="Pasta"))

    async def test_chef_timeout_is_reported(self):
        def chef(_):
            time.sleep(0.08)
            return {"recipe_details": recipe()}

        async def media(_):
            return {"media_links": {"image_url": "image"}}

        graph = build_recipe_graph(chef, media, chef_timeout=0.01)
        with self.assertRaises(TimeoutError):
            await graph.ainvoke(AgentState(selected_dish="Pasta"))

    async def test_menu_only_graph_still_invokes_chef_once(self):
        calls = []

        def chef(state):
            calls.append(state.cuisine)
            return {"menu_options": [{"dish_name": "Pasta", "teaser": "Easy", "primary_protein": "Beans"}]}

        workflow = StateGraph(AgentState)
        workflow.add_node("chef", chef)
        workflow.add_edge(START, "chef")
        workflow.add_edge("chef", END)
        result = await workflow.compile().ainvoke(AgentState(cuisine="Italian"))
        self.assertEqual(calls, ["Italian"])
        self.assertEqual(result["menu_options"][0]["dish_name"], "Pasta")


if __name__ == "__main__":
    unittest.main()
