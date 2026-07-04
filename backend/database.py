import os
import json
from redis import Redis
from schemas import RecipeSchema

REDIS_URL = os.getenv("REDIS_URL")
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)

def get_cached_recipe(dish_name: str) -> dict | None:
    """
    Checks the Redis cache layer for an existing recipe record to bypass LLM latency.
    """
    cache_key = f"recipe:{dish_name.lower().replace(' ', '_')}"
    cached_data = redis_client.get(cache_key)
    
    if cached_data:
        print(f"🎯 [CACHE HIT]: Serving '{dish_name}' instantly from Cloud Redis!")
        return json.loads(cached_data)
        
    print(f"💨 [CACHE MISS]: '{dish_name}' not found locally. Initiating RAG Pipeline...")
    return None


def save_recipe_to_cache(dish_name: str, recipe_data: dict):
    """
    Caches the generated recipe data structure and updates analytics profiles.
    """
    cache_key = f"recipe:{dish_name.lower().replace(' ', '_')}"
    
    # Store complete structured data string in Redis
    redis_client.set(cache_key, json.dumps(recipe_data))
    print(f"💾 [CACHE HYDRATED]: '{dish_name}' safely indexed inside Redis Cloud.")
    
    # Track metrics for the recommendation system 
    # (Logs how many times this dish has been chosen across your platform)
    redis_client.hincrby("analytics:dish_popularity", dish_name, 1)
    
    # Track user interaction history list (Using a default user ID for testing)
    redis_client.sadd("user:harsh_123:tried_dishes", dish_name)