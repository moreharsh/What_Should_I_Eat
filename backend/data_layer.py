import os
import json
import asyncio
from redis import Redis
from databricks import sql
from recipe_cache import recipe_cache_key


REDIS_URL = os.getenv("REDIS_URL")
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)

DB_HOST = os.getenv("DATABRICKS_SERVER_HOSTNAME")
DB_PATH = os.getenv("DATABRICKS_HTTP_PATH")
DB_TOKEN = os.getenv("DATABRICKS_PERSONAL_ACCESS_TOKEN")

def get_cached_recipe(dish_name: str, cuisine: str, dietary_restrictions=None) -> dict | None:
    """Look up only a v2 recipe variant; never trust legacy dish-only cache entries."""
    cache_key = recipe_cache_key(dish_name, cuisine, dietary_restrictions)
    cached_data = redis_client.get(cache_key)
    return json.loads(cached_data) if cached_data else None


def save_recipe_to_cache(dish_name: str, cuisine: str, recipe_data: dict, dietary_restrictions=None):
    """Persist one cuisine- and dietary-specific recipe variant."""
    cache_key = recipe_cache_key(dish_name, cuisine, dietary_restrictions)
    redis_client.set(cache_key, json.dumps(recipe_data))
    return cache_key

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

async def log_profile_event_to_databricks(
    user_id: str, username: str, event_type: str, dish_name: str = "",
    cuisine: str = "", dietary_restrictions=None,
):
    """Append profile activity to a new Delta table; never block the live API.

    This is analytics storage, not authentication or the live favorites source.
    The opaque bearer token is deliberately NEVER stored in Databricks.
    """
    if not all([DB_HOST, DB_PATH, DB_TOKEN]):
        return
    if event_type not in {"profile_created", "viewed", "saved", "unsaved", "tried", "untried"}:
        raise ValueError("Unknown profile event")

    def write_event():
        try:
            with sql.connect(
                server_hostname=DB_HOST, http_path=DB_PATH, access_token=DB_TOKEN
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS default.app_user_events (
                            user_id STRING,
                            username STRING,
                            event_type STRING,
                            dish_name STRING,
                            cuisine STRING,
                            dietary_restrictions STRING,
                            event_at TIMESTAMP
                        ) USING DELTA
                    """)
                    cursor.execute("""
                        INSERT INTO default.app_user_events
                            (user_id, username, event_type, dish_name, cuisine,
                             dietary_restrictions, event_at)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP())
                    """, (
                        user_id, username, event_type, dish_name, cuisine,
                        json.dumps(dietary_restrictions or []),
                    ))
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Databricks profile event logging failed: event_type=%s", event_type
            )

    await asyncio.to_thread(write_event)
