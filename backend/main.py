import os
import json
import logging
import http.client
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List, Optional

from langgraph.graph import StateGraph, END
from schemas import AgentState, RecipeSchema, MenuSchema
from agents import chef_agent, media_agent

from data_layer import redis_client, log_interaction_to_databricks, log_profile_event_to_databricks
from recipe_workflow import build_recipe_graph, run_media_safely
from recipe_cache import (
    normalize_dietary_restrictions, recipe_cache_key, user_history_key,
    user_saved_key, user_viewed_key,
)
from user_sessions import create_profile, get_profile, revoke_profile
from guest_api import router as guest_router, limit_guest_generation
from account_auth import router as account_router
from admin_api import router as admin_router
from maintenance_api import router as maintenance_router
from dietary_validation import incompatible_ingredients, SUPPORTED_RESTRICTIONS

logger = logging.getLogger(__name__)

app = FastAPI(title="What Should I Eat?")
app.include_router(admin_router)
app.include_router(account_router)
app.include_router(guest_router)
app.include_router(maintenance_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

menu_workflow = StateGraph(AgentState)
menu_workflow.add_node("chef", chef_agent)
menu_workflow.set_entry_point("chef")
menu_workflow.add_edge("chef", END)
menu_graph = menu_workflow.compile()

recipe_graph = build_recipe_graph(chef_agent, media_agent)


class MenuRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cuisine: str
    dietary_restrictions: List[str] = Field(default_factory=list)

    @field_validator("dietary_restrictions")
    @classmethod
    def validate_restrictions(cls, values):
        normalized = normalize_dietary_restrictions(values)
        if set(normalized) - SUPPORTED_RESTRICTIONS:
            raise ValueError("Unsupported dietary restriction")
        return normalized



class RecipeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_dish: str
    dietary_restrictions: List[str] = Field(default_factory=list)
    cuisine: Optional[str] = "unassigned"

    @field_validator("dietary_restrictions")
    @classmethod
    def validate_restrictions(cls, values):
        normalized = normalize_dietary_restrictions(values)
        if set(normalized) - SUPPORTED_RESTRICTIONS:
            raise ValueError("Unsupported dietary restriction")
        return normalized



class MenuDashboardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cuisine: str
    dietary_restrictions: List[str] = Field(default_factory=list)

    @field_validator("dietary_restrictions")
    @classmethod
    def validate_restrictions(cls, values):
        normalized = normalize_dietary_restrictions(values)
        if set(normalized) - SUPPORTED_RESTRICTIONS:
            raise ValueError("Unsupported dietary restriction")
        return normalized




class ProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str


class RecipeActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_dish: str
    cuisine: str
    dietary_restrictions: List[str] = Field(default_factory=list)
    action: str
    active: bool = True

    @field_validator("dietary_restrictions")
    @classmethod
    def validate_restrictions(cls, values):
        normalized = normalize_dietary_restrictions(values)
        if set(normalized) - SUPPORTED_RESTRICTIONS:
            raise ValueError("Unsupported dietary restriction")
        return normalized

    @field_validator("action")
    @classmethod
    def validate_action(cls, value):
        if value not in {"saved", "tried"}:
            raise ValueError("Expected 'saved' or 'tried'")
        return value


@app.post("/api/session")
async def start_session(request: ProfileRequest, background_tasks: BackgroundTasks):
    try:
        profile = create_profile(request.username)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    background_tasks.add_task(
        log_profile_event_to_databricks, profile["user_id"],
        profile["username"], "profile_created",
    )
    return profile


@app.get("/api/session")
async def read_session(profile=Depends(get_profile)):
    return profile


@app.delete("/api/session")
async def end_session(
    authorization: str = Header(default=""), profile=Depends(get_profile)
):
    revoke_profile(authorization.removeprefix("Bearer "))
    return {"ok": True}


@app.post("/api/recipe-action")
async def update_recipe_action(
    request: RecipeActionRequest, background_tasks: BackgroundTasks,
    profile=Depends(get_profile),
):
    cuisine = request.cuisine.strip().lower()
    restrictions = normalize_dietary_restrictions(request.dietary_restrictions)
    cache_key = recipe_cache_key(request.selected_dish, cuisine, restrictions)
    cached = redis_client.get(cache_key)
    if not cached:
        raise HTTPException(status_code=404, detail="Recipe not found. Open it first")
    try:
        record = json.loads(cached)
        if (
            not isinstance(record, dict)
            or record.get("cuisine") != cuisine
            or normalize_dietary_restrictions(record.get("dietary_restrictions", [])) != restrictions
            or not record.get("recipe_text")
        ):
            raise ValueError("Cached recipe does not match request")
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=404, detail="Recipe variant not found") from None
    history_key = (
        user_saved_key(profile["user_id"])
        if request.action == "saved" else user_history_key(profile["user_id"])
    )
    if request.active:
        redis_client.sadd(history_key, cache_key)
    else:
        redis_client.srem(history_key, cache_key)
    event_type = request.action if request.active else (
        "unsaved" if request.action == "saved" else "untried"
    )
    background_tasks.add_task(
        log_profile_event_to_databricks, profile["user_id"], profile["username"],
        event_type, request.selected_dish, cuisine, restrictions,
    )
    return {"action": request.action, "active": request.active}


@app.post("/api/menu")
async def get_menu_options(
    request: MenuRequest, authorization: str = Header(default=""),
):
    # The existing anonymous /api/menu contract remains supported, while
    # guest sessions are subject to a specific bounded demo allowance.
    if authorization:
        limit_guest_generation(get_profile(authorization), "menu")
    try:
        initial_state = AgentState(
            cuisine=request.cuisine,
            dietary_preferences=normalize_dietary_restrictions(request.dietary_restrictions)
        )

        # The Chef node is synchronous; LangGraph handles it in an executor.
        # Never run blocking Gemini requests directly in an async FastAPI route.
        result = await menu_graph.ainvoke(initial_state)
        options = result.get("menu_options") if isinstance(result, dict) else None
        validated = MenuSchema.model_validate({"options": options})
        if len(validated.options) != 5:
            raise ValueError("The Chef agent did not return five menu options")
        names = [item.dish_name.strip().casefold() for item in validated.options]
        if len(set(names)) != 5:
            raise ValueError("The Chef agent returned duplicate menu options")
        return {"menu_options": validated.model_dump()["options"]}

    except Exception:
        # Log the exception and traceback to Render, not to the browser.
        logger.exception(
            "Menu generation failed: cuisine=%s, dietary_restrictions=%s",
            request.cuisine, request.dietary_restrictions,
        )
        raise HTTPException(
            status_code=502, detail="Menu generation is temporarily unavailable. Please retry."
        ) from None


@app.post("/api/recipe")
async def get_recipe_details(
    request: RecipeRequest, background_tasks: BackgroundTasks,
    profile=Depends(get_profile),
):
    limit_guest_generation(profile, "recipe")
    try:
        # 🚀 1. STANDARDIZE THE CACHE KEY FIRST (Fixes Cache Miss Bug)
        cuisine_context = request.cuisine.strip().lower() if request.cuisine else "unassigned"
        dietary_restrictions = normalize_dietary_restrictions(request.dietary_restrictions)
        cache_key = recipe_cache_key(request.selected_dish, cuisine_context, dietary_restrictions)

        def record_view():
            # Record only successful recipe responses, not failed attempts.
            redis_client.sadd(user_viewed_key(profile["user_id"]), cache_key)
            background_tasks.add_task(
                log_profile_event_to_databricks, profile["user_id"], profile["username"],
                "viewed", request.selected_dish, cuisine_context, dietary_restrictions,
            )

        # Read directly from Redis Cloud using the uniform key structure
        cached_raw = redis_client.get(cache_key)

        if cached_raw:
            try:
                parsed_cache = json.loads(cached_raw)
                if not isinstance(parsed_cache, dict):
                    raise ValueError("Invalid cache record")
                if parsed_cache.get("cuisine") != cuisine_context:
                    raise ValueError("Cached cuisine mismatch")
                if normalize_dietary_restrictions(parsed_cache.get("dietary_restrictions", [])) != dietary_restrictions:
                    raise ValueError("Cached dietary restrictions mismatch")
                recipe_content = RecipeSchema.model_validate(parsed_cache["recipe_text"]).model_dump()
                if incompatible_ingredients(recipe_content, dietary_restrictions):
                    raise ValueError("Cached recipe has conflicting ingredients")
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                # Never serve an unverified cache entry, or repeatedly fail on it.
                print(f"Invalid recipe cache entry; regenerating: {exc}")
                redis_client.delete(cache_key)
            else:
                media_result = await run_media_safely(
                    AgentState(selected_dish=request.selected_dish), media_agent
                )
                background_tasks.add_task(
                    log_interaction_to_databricks,
                    profile["user_id"], request.selected_dish, cuisine_context, "CachedCuisine", "",
                )
                record_view()
                return {
                    "recipe_details": recipe_content,
                    "media_links": media_result.get("media_links"),
                    "is_saved": cache_key in redis_client.smembers(user_saved_key(profile["user_id"])),
                    "is_tried": cache_key in redis_client.smembers(user_history_key(profile["user_id"])),
                }

        try:
            recipe_state = AgentState(
                cuisine=cuisine_context,
                selected_dish=request.selected_dish,
                dietary_preferences=normalize_dietary_restrictions(request.dietary_restrictions)
            )
            result = await recipe_graph.ainvoke(recipe_state)
            fresh_recipe = result.get("recipe_details")
            media_links = result.get("media_links")
        except Exception:
            # Optional Ollama fallback remains tracked in issue #6.
            logger.exception("Recipe generation failed: chef branch unavailable")
            raise HTTPException(
                status_code=502, detail="Recipe generation unavailable; please retry"
            ) from None

        if not fresh_recipe:
            raise HTTPException(status_code=502, detail="Recipe generation returned no recipe")

        if isinstance(fresh_recipe, str):
            try:
                fresh_recipe = json.loads(fresh_recipe)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=502, detail="Recipe generation returned invalid JSON") from exc
        try:
            parsed_fresh_recipe = RecipeSchema.model_validate(fresh_recipe).model_dump()
            conflicts = incompatible_ingredients(parsed_fresh_recipe, dietary_restrictions)
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="Recipe generation returned invalid ingredients") from exc
        if conflicts:
            raise HTTPException(
                status_code=502,
                detail="Generated recipe includes ingredients conflicting with dietary restrictions; try again.",
            )

        recipe_metadata = {
            "dish_name": request.selected_dish,
            "cuisine": cuisine_context,
            "recipe_text": parsed_fresh_recipe,
            "dietary_restrictions": dietary_restrictions,
            "prep_time": parsed_fresh_recipe.get("prep_time", "30 mins") if isinstance(parsed_fresh_recipe, dict) else "30 mins",
            "difficulty": "Medium",
            "chef_pro_tip": parsed_fresh_recipe.get("chef_pro_tip", "Enjoy it hot!") if isinstance(parsed_fresh_recipe, dict) else "Enjoy it hot!"
        }

        # Write using the exact same uniform cache_key variable
        redis_client.set(cache_key, json.dumps(recipe_metadata))

        # Do not automatically mark a viewed recipe as saved or cooked.

        # 🚀 NEW: Turn your fresh, structured recipe object into a string payload for the data lake
        recipe_string_payload = json.dumps(parsed_fresh_recipe)
        # 🚀 FIX: Pass all 4 updated parameters to your background worker task
        background_tasks.add_task(
            log_interaction_to_databricks,
            profile["user_id"],
            request.selected_dish,
            cuisine_context,        # Argument 3: actual cuisine context
            "DiscoveryFeed",        # Argument 4: tracking context
            recipe_string_payload   # Argument 5: full stringified recipe data!
        )

        record_view()
        return {
            "recipe_details": parsed_fresh_recipe,
            "media_links": media_links,
            "is_saved": cache_key in redis_client.smembers(user_saved_key(profile["user_id"])),
            "is_tried": cache_key in redis_client.smembers(user_history_key(profile["user_id"])),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected recipe endpoint failure")
        raise HTTPException(status_code=500, detail="Recipe service unavailable; please retry") from None


@app.post("/api/menu-dashboard")
async def get_menu_dashboard(request: MenuDashboardRequest, profile=Depends(get_profile)):
    try:
        history_key = user_history_key(profile["user_id"])
        saved_key = user_saved_key(profile["user_id"])
        viewed_key = user_viewed_key(profile["user_id"])
        cached_recipe_keys = redis_client.smembers(history_key)
        saved_recipe_keys = redis_client.smembers(saved_key)
        viewed_recipe_keys = redis_client.smembers(viewed_key)
        requested_restrictions = normalize_dietary_restrictions(request.dietary_restrictions)

        previously_tried = []
        saved_favorites = []
        viewed_recipes = []
        target_cuisine = request.cuisine.lower()

        for cache_key in sorted(cached_recipe_keys | saved_recipe_keys | viewed_recipe_keys):
            # Legacy unscoped entries must not bypass dietary constraints.
            if not cache_key.startswith("recipe:v2:"):
                continue
            cached_raw = redis_client.get(cache_key)
            if cached_raw:
                try:
                    recipe_data = json.loads(cached_raw)
                    if isinstance(recipe_data, dict):
                        cached_cuisine = recipe_data.get("cuisine", "").lower()
                        cached_restrictions = normalize_dietary_restrictions(recipe_data.get("dietary_restrictions", []))
                        if cached_cuisine == target_cuisine and cached_restrictions == requested_restrictions:
                            item = {
                                "dish_name": recipe_data.get("dish_name", ""),
                                "dietary_restrictions": cached_restrictions,
                                "prep_time": recipe_data.get("prep_time", "30 mins"),
                                "difficulty": recipe_data.get("difficulty", "Medium"),
                                "teaser": recipe_data.get("chef_pro_tip", "A favorite recipe!")[:85] + "...",
                                "saved": cache_key in saved_recipe_keys,
                                "tried": cache_key in cached_recipe_keys,
                                "viewed": cache_key in viewed_recipe_keys,
                            }
                            if cache_key in cached_recipe_keys:
                                previously_tried.append(item)
                            if cache_key in saved_recipe_keys:
                                saved_favorites.append(item)
                            if cache_key in viewed_recipe_keys:
                                viewed_recipes.append(item)
                except Exception as e:
                    print(f"Skipping unparseable cache key {cache_key}: {e}")

        return {
            "has_history": bool(previously_tried or saved_favorites or viewed_recipes),
            "previously_tried": sorted(previously_tried, key=lambda item: item["dish_name"]),
            "saved_favorites": sorted(saved_favorites, key=lambda item: item["dish_name"]),
            "viewed_recipes": sorted(viewed_recipes, key=lambda item: item["dish_name"])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
def check_backend_health():
    print("Health Status checking")
    return {
        "Health_status_code": 200,
        "Health_status": "Active"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)