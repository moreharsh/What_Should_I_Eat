# test_env.py
import os
from dotenv import load_dotenv

load_dotenv()

print("Gemini Key Loaded:", bool(os.getenv("GEMINI_API_KEY")))
print("YouTube Key Loaded:", bool(os.getenv("YOUTUBE_API_KEY")))
print("Spoonacular Key Loaded:", bool(os.getenv("SPOONACULAR_API_KEY")))