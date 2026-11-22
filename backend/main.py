import os
import json
import http.client
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional

from langgraph.graph import StateGraph, END
from schemas import AgentState
from agents import chef_agent, media_agent

from data_layer import redis_client, log_interaction_to_databricks
from recipe_cache import normalize_dietary_restrictions, recipe_cache_key, user_history_key

app = FastAPI(title="What Should I Eat?")

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

recipe_workflow = StateGraph(AgentState)
recipe_workflow.add_node("chef", chef_agent)
recipe_workflow.add_node("media", media_agent)
recipe_workflow.set_entry_point("chef")
recipe_workflow.set_entry_point("media")
recipe_workflow.add_edge("chef", END)
recipe_workflow.add_edge("media", END)
recipe_graph = recipe_workflow.compile()


class MenuRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cuisine: str
    dietary_restrictions: List[str] = Field(default_factory=list)

class RecipeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_dish: str
    dietary_restrictions: List[str] = Field(default_factory=list)
    cuisine: Optional[str] = "unassigned"

class MenuDashboardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str
    cuisine: str
    dietary_restrictions: List[str] = Field(default_factory=list)


@app.post("/api/menu")
async def get_menu_options(request: MenuRequest):
    try:
        initial_state = AgentState(
            cuisine=request.cuisine,
            dietary_preferences=normalize_dietary_restrictions(request.dietary_restrictions)
        )

        result = menu_graph.invoke(initial_state)
        return {"menu_options": result.get("menu_options", [])}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recipe")
async def get_recipe_details(request: RecipeRequest, background_tasks: BackgroundTasks):
    try:
        # 🚀 1. STANDARDIZE THE CACHE KEY FIRST (Fixes Cache Miss Bug)
        cuisine_context = request.cuisine.strip().lower() if request.cuisine else "unassigned"
        dietary_restrictions = normalize_dietary_restrictions(request.dietary_restrictions)
        cache_key = recipe_cache_key(request.selected_dish, cuisine_context, dietary_restrictions)
        
        # Read directly from Redis Cloud using the uniform key structure
        cached_raw = redis_client.get(cache_key)
        
        if cached_raw:
            print(f"⚡ [PURE CACHE HIT]: Bypassing LLM Graph execution for '{request.selected_dish}'")
            recipe_content = cached_raw
            
            try:
                parsed_cache = json.loads(cached_raw) if isinstance(cached_raw, str) else cached_raw
                if isinstance(parsed_cache, dict) and "recipe_text" in parsed_cache:
                    recipe_content = parsed_cache["recipe_text"]
                    if isinstance(recipe_content, str):
                        recipe_content = json.loads(recipe_content)
            except Exception:
                pass 
            
            recipe_state = AgentState(selected_dish=request.selected_dish)
            media_result = await media_agent(recipe_state)
            redis_client.sadd(user_history_key("harsh_123"), cache_key)
            
            cuisine_context = request.cuisine.lower() if request.cuisine else "indian"
            
            background_tasks.add_task(
                log_interaction_to_databricks, 
                "harsh_123", 
                request.selected_dish, 
                cuisine_context,
                "CachedCuisine",
                ""
            )
            
            return {
                "recipe_details": recipe_content,
                "media_links": media_result.get("media_links")
            }

        try:
            recipe_state = AgentState(
                selected_dish=request.selected_dish,
                dietary_preferences=normalize_dietary_restrictions(request.dietary_restrictions)
            )
            result = await recipe_graph.ainvoke(recipe_state)
            fresh_recipe = result.get("recipe_details")
            media_links = result.get("media_links")
        except Exception as e:
            print(f"⚠️ Cloud Recipe Agent Mesh Failed: {e}. Routing to local engine...")
            from main import call_local_ollama_recipe_fallback_sync # Assumes defined helper
            local_raw_json = call_local_ollama_recipe_fallback_sync(request.selected_dish, cuisine_context, request.dietary_restrictions)
            
            fresh_recipe = json.loads(local_raw_json) if local_raw_json else None
            media_links = {"image_url": "", "youtube_embed_url": ""}
            
            if not fresh_recipe:
                fresh_recipe = {
                    "dish_name": request.selected_dish,
                    "prep_time": "25 mins",
                    "ingredients": ["Main authentic base ingredients"],
                    "instructions": ["Prepare locally via edge execution models."],
                    "chef_pro_tip": "Enjoy it hot!"
                }

        if fresh_recipe:
            parsed_fresh_recipe = fresh_recipe
            if isinstance(fresh_recipe, str):
                try: parsed_fresh_recipe = json.loads(fresh_recipe)
                except Exception: pass

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
            
            # Log to your personal Redis history set
            redis_client.sadd(user_history_key("harsh_123"), cache_key)
            
            # 🚀 NEW: Turn your fresh, structured recipe object into a string payload for the data lake
            recipe_string_payload = json.dumps(parsed_fresh_recipe)
            cuisine_context = request.cuisine.lower() if request.cuisine else "indian"
            
            # 🚀 FIX: Pass all 4 updated parameters to your background worker task
            background_tasks.add_task(
                log_interaction_to_databricks, 
                "harsh_123", 
                request.selected_dish, 
                cuisine_context,        # Argument 3: actual cuisine context
                "DiscoveryFeed",        # Argument 4: tracking context
                recipe_string_payload   # Argument 5: full stringified recipe data!
            )

        return {
            "recipe_details": parsed_fresh_recipe,
            "media_links": media_links
        }
        
    except Exception as e:
        print(f"💥 EXCEPTION IN RECIPE ENDPOINT: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/menu-dashboard")
async def get_menu_dashboard(request: MenuDashboardRequest):
    try:
        history_key = user_history_key(request.user_id)
        cached_recipe_keys = redis_client.smembers(history_key)
        requested_restrictions = normalize_dietary_restrictions(request.dietary_restrictions)
        
        previously_tried = []
        target_cuisine = request.cuisine.lower()
        
        for cache_key in cached_recipe_keys:
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
                            previously_tried.append({
                                "dish_name": recipe_data.get("dish_name", ""),
                                "dietary_restrictions": cached_restrictions,
                                "prep_time": recipe_data.get("prep_time", "30 mins"),
                                "difficulty": recipe_data.get("difficulty", "Medium"),
                                "teaser": recipe_data.get("chef_pro_tip", "A signature tried-and-true favorite!")[:85] + "..."
                            })
                except Exception as e:
                    print(f"Skipping unparseable cache key {cache_key}: {e}")

        return {
            "has_history": len(previously_tried) > 0,
            "previously_tried": previously_tried
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