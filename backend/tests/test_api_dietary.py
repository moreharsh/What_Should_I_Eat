"""FastAPI route regression tests with in-memory Redis and stubbed external agents."""
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from fastapi import Header, HTTPException
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

    def srem(self, key, value):
        self.sets.setdefault(key, set()).discard(value)

    def setex(self, key, _seconds, value):
        self.values[key] = value

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


class DishOption(BaseModel):
    dish_name: str
    teaser: str
    primary_protein: str


class MenuSchema(BaseModel):
    options: list[DishOption]


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
    schemas.MenuSchema = MenuSchema
    agents = types.ModuleType("agents")
    agents.chef_agent = lambda state: {}
    agents.media_agent = AsyncMock(return_value={"media_links": {"image_url": "", "youtube_embed_url": ""}})
    data_layer = types.ModuleType("data_layer")
    data_layer.redis_client = redis
    data_layer.log_interaction_to_databricks = AsyncMock()
    data_layer.log_profile_event_to_databricks = AsyncMock()
    sessions = types.ModuleType("user_sessions")
    def create_profile(username):
        if len(username) < 3 or len(username) > 24:
            raise ValueError("Invalid username")
        profile = {"user_id": f"session-{username}", "username": username, "token": f"token-{username}"}
        redis.setex(f"profile:session:{profile['token']}", 86400, json.dumps(profile))
        return profile
    def get_profile(authorization: str | None = Header(default=None)):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing session")
        record = redis.get(f"profile:session:{authorization[7:]}")
        if not record:
            raise HTTPException(status_code=401, detail="Invalid session")
        return json.loads(record)
    sessions.create_profile = create_profile
    sessions.get_profile = get_profile
    sessions.revoke_profile = lambda token: redis.delete(f"profile:session:{token}")
    recipe_workflow = types.ModuleType("recipe_workflow")
    recipe_workflow.build_recipe_graph = lambda *_: FakeStateGraph().compile()
    recipe_workflow.run_media_safely = AsyncMock(
        return_value={"media_links": {"image_url": "", "youtube_embed_url": ""}}
    )

    stubs = {
        "langgraph": langgraph_module,
        "langgraph.graph": graph_module,
        "schemas": schemas,
        "agents": agents,
        "data_layer": data_layer,
        "recipe_workflow": recipe_workflow,
        "user_sessions": sessions,
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
        response = self.client.post("/api/session", json={"username": "test_user"})
        self.assertEqual(response.status_code, 200, response.text)
        self.client.headers.update({"Authorization": f"Bearer {response.json()['token']}"})

    def recipe_values(self):
        return {key: value for key, value in self.redis.values.items() if key.startswith("recipe:v2:")}

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
        self.assertEqual(len(self.recipe_values()), 2)

    def test_corrupt_cache_is_evicted_and_regenerated(self):
        self.assertEqual(self.post_recipe(["vegan"]).status_code, 200)
        key = next(iter(self.recipe_values()))
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
        self.assertFalse(self.recipe_values())

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

    def test_menu_returns_validated_items(self):
        self.app.menu_graph.ainvoke.return_value = {"menu_options": [
            {"dish_name": name, "teaser": "Fresh", "primary_protein": "Beans"}
            for name in ("Tacos", "Burritos", "Tamales", "Enchiladas", "Quesadillas")
        ]}
        response = self.client.post("/api/menu", json={
            "cuisine": "Mexican", "dietary_restrictions": ["Vegan"],
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["menu_options"][0]["dish_name"], "Tacos")
        self.app.menu_graph.ainvoke.assert_awaited_once()

    def test_duplicate_menu_options_are_safe_502(self):
        self.app.menu_graph.ainvoke.return_value = {"menu_options": [
            {"dish_name": "Tacos", "teaser": "Fresh", "primary_protein": "Beans"}
        ] * 5}
        response = self.client.post("/api/menu", json={
            "cuisine": "Mexican", "dietary_restrictions": [],
        })
        self.assertEqual(response.status_code, 502)

    def test_unexpected_recipe_error_does_not_expose_internal_details(self):
        self.app.recipe_graph.ainvoke.side_effect = RuntimeError("secret backend error")
        response = self.post_recipe([])
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("secret backend error", response.text)

    def test_menu_model_exception_is_safe_502(self):
        self.app.menu_graph.ainvoke.side_effect = RuntimeError("private provider detail")
        response = self.client.post("/api/menu", json={
            "cuisine": "Italian", "dietary_restrictions": [],
        })
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private provider detail", response.text)

    def test_menu_invalid_model_payload_is_safe_502(self):
        self.app.menu_graph.ainvoke.return_value = {"menu_options": None}
        response = self.client.post("/api/menu", json={
            "cuisine": "Indian", "dietary_restrictions": [],
        })
        self.assertEqual(response.status_code, 502)

    def test_menu_rejects_unsupported_diet_before_model(self):
        response = self.client.post("/api/menu", json={
            "cuisine": "Italian", "dietary_restrictions": ["unknown-diet"],
        })
        self.assertEqual(response.status_code, 422)
        self.app.menu_graph.ainvoke.assert_not_awaited()

    def test_dashboard_filters_recipe_variants(self):
        self.assertEqual(self.post_recipe(["vegan"]).status_code, 200)
        dashboard = self.client.post("/api/menu-dashboard", json={
            "cuisine": "Italian", "dietary_restrictions": ["vegan"],
        })
        self.assertEqual(dashboard.status_code, 200, dashboard.text)
        self.assertEqual(len(dashboard.json()["previously_tried"]), 0)
        action = self.client.post("/api/recipe-action", json={
            "selected_dish": "Pasta", "cuisine": "Italian",
            "dietary_restrictions": ["vegan"], "action": "tried", "active": True,
        })
        self.assertEqual(action.status_code, 200, action.text)
        dashboard = self.client.post("/api/menu-dashboard", json={
            "cuisine": "Italian", "dietary_restrictions": ["vegan"],
        })
        self.assertEqual(len(dashboard.json()["previously_tried"]), 1)
        other = self.client.post("/api/menu-dashboard", json={
            "cuisine": "Italian", "dietary_restrictions": [],
        })
        self.assertEqual(other.status_code, 200, other.text)
        self.assertEqual(len(other.json()["previously_tried"]), 0)

    def test_viewed_only_recipe_appears_in_dashboard_after_returning_to_profile(self):
        first_login = self.client.post("/api/session", json={"username": "returning_cook"})
        self.assertEqual(first_login.status_code, 200)
        self.client.headers["Authorization"] = f"Bearer {first_login.json()['token']}"
        recipe_response = self.post_recipe(["vegan"])
        self.assertEqual(recipe_response.status_code, 200, recipe_response.text)
        first_dashboard = self.client.post("/api/menu-dashboard", json={
            "cuisine": "Italian", "dietary_restrictions": ["vegan"],
        })
        self.assertEqual(first_dashboard.status_code, 200)
        self.assertEqual(len(first_dashboard.json()["viewed_recipes"]), 1)
        self.assertEqual(first_dashboard.json()["saved_favorites"], [])
        self.assertEqual(first_dashboard.json()["previously_tried"], [])

        self.assertEqual(self.client.delete("/api/session").status_code, 200)
        second_login = self.client.post("/api/session", json={"username": "returning_cook"})
        self.assertEqual(second_login.status_code, 200)
        self.client.headers["Authorization"] = f"Bearer {second_login.json()['token']}"
        second_dashboard = self.client.post("/api/menu-dashboard", json={
            "cuisine": "Italian", "dietary_restrictions": ["vegan"],
        })
        self.assertEqual(second_dashboard.status_code, 200)
        self.assertTrue(second_dashboard.json()["has_history"])
        self.assertEqual(second_dashboard.json()["viewed_recipes"][0]["dish_name"], "Pasta")

    def test_viewed_history_is_not_exposed_to_another_user(self):
        self.assertEqual(self.post_recipe(["vegan"]).status_code, 200)
        response = self.client.post("/api/session", json={"username": "other_user"})
        self.assertEqual(response.status_code, 200)
        self.client.headers["Authorization"] = f"Bearer {response.json()['token']}"
        dashboard = self.client.post("/api/menu-dashboard", json={
            "cuisine": "Italian", "dietary_restrictions": ["vegan"],
        })
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["viewed_recipes"], [])

    def test_profiles_are_isolated_and_recipe_open_is_not_tried(self):
        response = self.post_recipe(["vegan"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["is_saved"])
        self.assertFalse(response.json()["is_tried"])
        action = self.client.post("/api/recipe-action", json={
            "selected_dish": "Pasta", "cuisine": "Italian",
            "dietary_restrictions": ["vegan"], "action": "saved",
        })
        self.assertEqual(action.status_code, 200, action.text)
        bob = self.client.post("/api/session", json={"username": "bob_user"})
        self.assertEqual(bob.status_code, 200)
        with self.client:
            self.client.headers["Authorization"] = f"Bearer {bob.json()['token']}"
            other = self.client.post("/api/menu-dashboard", json={
                "cuisine": "Italian", "dietary_restrictions": ["vegan"],
            })
            self.assertEqual(other.status_code, 200, other.text)
            self.assertFalse(other.json()["saved_favorites"])
            self.assertFalse(other.json()["previously_tried"])
            self.assertEqual(self.post_recipe(["vegan"]).json()["is_saved"], False)

    def test_actions_do_not_cross_recipe_variants(self):
        self.assertEqual(self.post_recipe(["vegan"]).status_code, 200)
        saved = self.client.post("/api/recipe-action", json={
            "selected_dish": "Pasta", "cuisine": "Italian",
            "dietary_restrictions": ["vegan"], "action": "saved",
        })
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(self.post_recipe([]).json()["is_saved"], False)

    def test_unmark_actions_and_session_authorization(self):
        self.assertEqual(self.post_recipe([]).status_code, 200)
        payload = {
            "selected_dish": "Pasta", "cuisine": "Italian",
            "dietary_restrictions": [], "action": "tried",
        }
        self.assertEqual(self.client.post("/api/recipe-action", json=payload).status_code, 200)
        self.assertTrue(self.post_recipe([]).json()["is_tried"])
        payload["active"] = False
        self.assertEqual(self.client.post("/api/recipe-action", json=payload).status_code, 200)
        self.assertFalse(self.post_recipe([]).json()["is_tried"])
        self.client.headers.pop("Authorization")
        self.assertEqual(self.client.post("/api/recipe", json={
            "selected_dish": "Pasta", "cuisine": "Italian",
        }).status_code, 401)
        self.assertEqual(self.client.post("/api/menu-dashboard", json={
            "cuisine": "Italian",
        }).status_code, 401)


if __name__ == "__main__":
    unittest.main()
