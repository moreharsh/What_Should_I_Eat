# backend/agents.py
import os
import json
import asyncio
import time
import httpx
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from dotenv import load_dotenv
from schemas import AgentState

load_dotenv()
client = genai.Client()

MODEL_POOL = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite"
]

def generate_content_with_retry(contents: str, config: types.GenerateContentConfig, max_retries_per_model=2):
    last_exception = None

    for model in MODEL_POOL:
        delay = 1.5
        print(f"📡 Attempting execution using model: {model}")
        
        for attempt in range(max_retries_per_model):
            try:
                response = client.models.generate_content(
                    model=model, 
                    contents=contents, 
                    config=config
                )
                print(f"✅ Success using {model}")
                return response
                
            except ClientError as e:
                last_exception = e
                if e.code in [429, 503]:
                    print(f"⚠️ Model {model} rate limited/unavailable. Backing off {delay}s...")
                    time.sleep(delay)
                    delay *= 2
                    continue
                break
            except Exception as e:
                last_exception = e
                print(f"💥 Unexpected error on {model}: {e}")
                break
                
        print(f"🔄 Model {model} exhausted. Cascading to next available runtime...")

    raise RuntimeError(f"All models in the high-availability pool failed. Last error: {last_exception}")


# --- NODE 1: CHEF AGENT ---
def chef_agent(state: AgentState) -> dict:
    if state.selected_dish:
        prompt = (
            f"Search Google for an authentic recipe for '{state.selected_dish}' matching constraints: {', '.join(state.dietary_preferences)}. "
            f"Output your complete answer strictly in the following JSON template format:\n"
            f'{{"dish_name": "...", "prep_time": "...", "cook_time": "...", "servings": "4-6 servings", "ingredients": ["...", "..."], "instructions": ["...", "..."], "chef_pro_tip": "..."}}'
        )
        
        response = generate_content_with_retry(
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}],  
                system_instruction="You are a Michelin-star chef. You must output raw JSON text only matching the exact user schema key format. Do not wrap in ```json markers."
            )
        )
        
        clean_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
        return {"recipe_details": json.loads(clean_text)}


    # --- PHASE 1 FLOW: Generate the initial 5 options ---
    prompt = (
        f"Search Google to find 5 popular, distinct, authentic dishes from '{state.cuisine}' cuisine that respect constraints: {', '.join(state.dietary_preferences)}. "
        f"Output your complete answer strictly in the following JSON template format:\n"
        f'{{"options": [{{"dish_name": "...", "teaser": "...", "primary_protein": "..."}}]}}'
    )
    
    response = generate_content_with_retry(
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[{"google_search": {}}],  
            system_instruction="You are an expert culinary curator. You must output raw JSON text only matching the exact template format. Do not wrap in markdown tags."
        )
    )
    
    clean_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    parsed_data = json.loads(clean_text)
    return {"menu_options": parsed_data["options"]}



# --- NODE 2: MEDIA BROKER AGENT ---
async def media_agent(state: AgentState) -> dict:
    dish_name = state.selected_dish
    if not dish_name:
        return {}

    yt_key = os.getenv("YOUTUBE_API_KEY")
    spoon_key = os.getenv("SPOONACULAR_API_KEY")

    async def fetch_youtube_link(query: str) -> str:
        """Queries YouTube v3 Search Endpoint for an embeddable video ID."""
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "id",
            "q": f"{query} recipe tutorial",
            "type": "video",
            "maxResults": 1,
            "key": yt_key
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])
                    if items:
                        video_id = items[0]["id"]["videoId"]
                        return f"https://www.youtube.com/embed/{video_id}"
        except Exception as e:
            print(f"❌ YouTube Fetch Failed: {e}")
        return f"https://www.youtube.com/embed?listType=search&list={query.replace(' ', '+')}+recipe"

    async def fetch_food_image(query: str) -> str:
        if not spoon_key:
            print("⚠️ WARNING: SPOONACULAR_API_KEY is completely missing from .env")
            return "https://images.unsplash.com/photo-1546069901-ba9599a7e63c"

        url = "https://api.spoonacular.com/recipes/complexSearch"
        params = {
            "query": query,
            "number": 1,
            "apiKey": spoon_key
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=5.0)
                print(f"📡 Spoonacular API Status Code for '{query}': {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    
                    if results and "image" in results[0]:
                        img_url = results[0]["image"]
                        print(f"📸 Successfully matched image URL: {img_url}")
                        return img_url
                    else:
                        print(f"🔍 Spoonacular found 0 results for exact query: '{query}'. Trying fallback search...")
                        fallback_word = query.split()[0]
                        params["query"] = fallback_word
                        fallback_resp = await client.get(url, params=params, timeout=5.0)
                        if fallback_resp.status_code == 200:
                            fb_results = fallback_resp.json().get("results", [])
                            if fb_results:
                                return fb_results[0]["image"]
                                
        except Exception as e:
            print(f"❌ Spoonacular Network Fetch Failed: {e}")
            
        print("🎨 Using default Unsplash food cover placeholder.")
        return "https://images.unsplash.com/photo-1546069901-ba9599a7e63c"

    youtube_url, image_url = await asyncio.gather(
        fetch_youtube_link(dish_name),
        fetch_food_image(dish_name)
    )

    return {
        "media_links": {
            "youtube_embed_url": youtube_url,
            "image_url": image_url
        }
    }