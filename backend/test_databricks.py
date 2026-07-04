import os
from dotenv import load_dotenv
from databricks import sql

load_dotenv()

DB_HOST = os.getenv("DATABRICKS_SERVER_HOSTNAME")
DB_PATH = os.getenv("DATABRICKS_HTTP_PATH")
DB_TOKEN = os.getenv("DATABRICKS_PERSONAL_ACCESS_TOKEN")

print("📡 Connecting to Databricks Cloud SQL Endpoint...")
try:
    with sql.connect(server_hostname=DB_HOST, http_path=DB_PATH, personal_access_token=DB_TOKEN) as conn:
        with conn.cursor() as cursor:
            # Execute a basic low-overhead cluster calculation query
            cursor.execute("SELECT 1 + 1 AS connection_test")
            result = cursor.fetchone()
            print(f"✅ SUCCESS! Databricks computed connection test: {result[0] if result else 'No data'}")
except Exception as e:
    print(f"❌ DATABRICKS CONNECTION FAILED: {e}")