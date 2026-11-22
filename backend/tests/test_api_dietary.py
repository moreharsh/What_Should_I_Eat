"""FastAPI route regression tests with in-memory Redis and stubbed external agents."""
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from pydantic import BaseModel


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.sets = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value

    def delete(self, key):
        return int(self.values.pop(key, None) is not None)

    def sadd(self, key, value):
        self.sets.setdefault(key, set()).add(value)

    def smembers(self, key):
        return self.sets.get(key, set())


class FakeStateGraph:
    def __init__(self, *_):
        pass

    def add_node(self, *_):
        pass

    def set_entry_point(self, *_):
        pass

    def add_edge(self, *_):
        pass

    def compile(self):
        return types.SimpleNamespace(invoke=lambda *_: {}, ainvoke=AsyncMock())


class AgentState:
    def __init__(self, **values):
        self.__dict__.update(values)


class RecipeSchema(BaseModel):
    dish_name: str
    prep_time: str
    cook_time: str
    servings: str
    ingredients: list[str]
    instructions: list[str]
    chef_pro_tip: str


def sample_recipe(ingredients=None):
    return {
        "dish_name": "Pasta",
        "prep_time": "5 minutes",
        "cook_time": "10 minutes",
        "servings": "2",
        "ingredients": ingredients if ingredients is not None else ["tomato", "rice"],
        "instructions": ["Cook the ingredients."],
        "chef_pro_tip": "Serve warm.",
    }


def load_app():
    redis = FakeRedis()
    graph_module = types.ModuleType("langgraph.graph")
    graph_module.StateGraph = FakeStateGraph
    graph_module.END = "END"
    langgraph_module = types.ModuleType("langgraph")
    langgraph_module.graph = graph_module

    schemas = types.ModuleType("schemas")
    schemas.AgentState = AgentState
    schemas.RecipeSchema = RecipeSchema
    agents = types.ModuleType("agents")
    agents.chef_agent = lambda state: {}
    agents.media_agent = AsyncMock(return_value={"media_links": {"image_url": "", "youtube_embed_url": ""}})
    data_layer = types.ModuleType("data_layer")
    data_layer.redis_client = redis
    data_layer.log_interaction_to_databricks = AsyncMock()

    stubs = {
        "langgraph": langgraph_module,
        "langgraph.graph": graph_module,
        "schemas": schemas,
        "agents": agents,
        "data_layer": data_layer,
    }
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("dietary_test_main", root / "main.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    module.recipe_graph.ainvoke = AsyncMock(
        return_value={"recipe_details": sample_recipe(), "media_links": {"image_url": "", "youtube_embed_url": ""}}
    )
    return module, redis, TestClient(module.app)


class DietaryAPITests(unittest.TestCase):
    def setUp(self):
        self.app, self.redis, self.client = load_app()

    def post_recipe(self, restrictions):
        return self.client.post("/api/recipe", json={
            "selected_dish": "Pasta",
            "cuisine": "Italian",
            "dietary_restrictions": restrictions,
        })

    def test_restricted_cache_hit_and_unrestricted_miss_are_isolated(self):
        a = self.post_recipe(["Vegan"])
        self.assertEqual(a.status_code, 200, a.text)
        b = self.post_recipe(["vegan"])
        self.assertEqual(b.status_code, 200, b.text)
        self.assertEqual(self.app.recipe_graph.ainvoke.await_count, 1)
        c = self.post_recipe([])
        self.assertEqual(c.status_code, 200, c.text)
        self.assertEqual(self.app.recipe_graph.ainvoke.await_count, 2)
        self.assertEqual(len(self.redis.values), 2)

    def test_corrupt_cache_is_evicted_and_regenerated(self):
        self.assertEqual(self.post_recipe(["vegan"]).status_code, 200)
        key = next(iter(self.redis.values))
        self.redis.values[key] = "{corrupt json"
        result = self.post_recipe(["vegan"])
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.app.recipe_graph.ainvoke.await_count, 2)
        self.assertIsInstance(json.loads(self.redis.values[key]), dict)

    def test_incompatible_recipe_never_enters_cache(self):
        self.app.recipe_graph.ainvoke.return_value = {
            "recipe_details": sample_recipe(["200 g chicken", "tomato"]),
            "media_links": {},
        }
        result = self.post_recipe(["vegetarian"])
        self.assertEqual(result.status_code, 502)
        self.assertFalse(self.redis.values)

    def test_invalid_restrictions_are_rejected_before_invoking_model(self):
        result = self.post_recipe(["unknown-diet"])
        self.assertEqual(result.status_code, 422)
        self.app.recipe_graph.ainvoke.assert_not_awaited()

    def test_unknown_request_property_is_rejected(self):
        result = self.client.post("/api/recipe", json={
            "selected_dish": "Pasta", "cuisine": "Italian",
            "dietary_preferences": ["vegan"],
        })
        self.assertEqual(result.status_code, 422)

    def test_dashboard_filters_recipe_variants(self):
        self.assertEqual(self.post_recipe(["vegan"]).status_code, 200)
        dashboard = self.client.post("/api/menu-dashboard", json={
            "user_id": "harsh_123", "cuisine": "Italian", "dietary_restrictions": ["vegan"],
        })
        self.assertEqual(dashboard.status_code, 200, dashboard.text)
        self.assertEqual(len(dashboard.json()["previously_tried"]), 1)
        other = self.client.post("/api/menu-dashboard", json={
            "user_id": "harsh_123", "cuisine": "Italian", "dietary_restrictions": [],
        })
        self.assertEqual(other.status_code, 200, other.text)
        self.assertEqual(len(other.json()["previously_tried"]), 0)


if __name__ == "__main__":
    unittest.main()
