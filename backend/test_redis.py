# test_redis.py
import os
from dotenv import load_dotenv
from redis import Redis

load_dotenv()
REDIS_URL = os.getenv("REDIS_URL")

print("🔌 Attempting connection to Cloud Redis...")
print(f"🔗 Using URL: {REDIS_URL[:25]}... (Truncated for security)")

try:
    # Explicitly test parsing and connection execution
    client = Redis.from_url(REDIS_URL, decode_responses=True)
    
    # Run a basic ping command
    response = client.ping()
    if response:
        print("✅ SUCCESS! Successfully authenticated and pinged Cloud Redis.")
        
        # Test writing a sample string value
        client.set("test_connection_key", "working")
        print("💾 Success: Wrote test key to hot database storage.")
        
except Exception as e:
    print(f"❌ CONNECTION FAILED: {e}")