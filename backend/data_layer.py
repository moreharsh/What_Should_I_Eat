import os
import json
import asyncio
from redis import Redis
from databricks import sql


REDIS_URL = os.getenv("REDIS_URL")
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)

DB_HOST = os.getenv("DATABRICKS_SERVER_HOSTNAME")
DB_PATH = os.getenv("DATABRICKS_HTTP_PATH")
DB_TOKEN = os.getenv("DATABRICKS_PERSONAL_ACCESS_TOKEN")

def get_cached_recipe(dish_name: str) -> dict | None:
    """Read-Through Cache: Pulls raw recipe payloads instantly from Redis."""
    cache_key = f"recipe:{dish_name.lower().replace(' ', '_')}"
    cached_data = redis_client.get(cache_key)
    if cached_data:
        print(f"🎯 [REDIS CACHE HIT]: Found '{dish_name}' in cloud hot storage.")
        return json.loads(cached_data)
    print(f"💨 [REDIS CACHE MISS]: '{dish_name}' not cached. Routing to Agent Mesh...")
    return None

def save_recipe_to_cache(dish_name: str, recipe_data: dict):
    """Hydrates Cloud Redis with structured text JSON blocks."""
    cache_key = f"recipe:{dish_name.lower().replace(' ', '_')}"
    redis_client.set(cache_key, json.dumps(recipe_data))
    print(f"💾 [REDIS HYDRATED]: '{dish_name}' saved to hot memory cache.")


async def log_interaction_to_databricks(user_id: str, dish_name: str, cuisine: str, tracking_context: str, recipe_details_json: str = ""):
    """
    Cold Path Worker: Asynchronously logs analytical data to Databricks.
    Now tracks both actual cuisine AND the tracking context layer.
    """
    if not all([DB_HOST, DB_PATH, DB_TOKEN]):
        print("⚠️ Databricks credentials missing. Skipping cloud lakehouse logging.")
        return

    def execute_insert():
        try:
            escaped_recipe = recipe_details_json.replace("'", "''") if recipe_details_json else ""
            
            with sql.connect(
                server_hostname=DB_HOST, 
                http_path=DB_PATH, 
                access_token=DB_TOKEN  
            ) as conn:
                with conn.cursor() as cursor:
                    # 🚀 REMOVED THE RESTRICTED SET LINE

                    # Clean, fresh table layout creation script
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS default.user_clicks (
                            user_id STRING, 
                            dish_name STRING, 
                            cuisine STRING, 
                            tracking_context STRING,
                            timestamp TIMESTAMP,
                            recipe_details STRING
                        ) USING DELTA
                    """)
                    
                    cursor.execute(f"""
                        INSERT INTO default.user_clicks 
                        VALUES (
                            '{user_id}', 
                            '{dish_name}', 
                            '{cuisine}', 
                            '{tracking_context}', 
                            CURRENT_TIMESTAMP(), 
                            '{escaped_recipe}'
                        )
                    """)
            print(f"🚀 [DATABRICKS RETENTION]: Saved tracking layout for '{dish_name}' down to Delta Lake.")
        except Exception as e:
            print(f"❌ Databricks Background Logging Exception caught safely: {e}")

    await asyncio.to_thread(execute_insert)