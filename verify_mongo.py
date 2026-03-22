import asyncio
import os
from pymongo import AsyncMongoClient
from dotenv import load_dotenv

async def test():
    # Load .env from its absolute path
    env_path = r"c:\Users\DELL\.gemini\antigravity\scratch\AnonXMusic\.env"
    load_dotenv(env_path)
    
    mongo_url = os.getenv("MONGO_URL")
    print(f"Testing MongoDB with URL: {mongo_url}")
    if not mongo_url or "xxxxx" in mongo_url:
        print("ALERT: MONGO_URL appears to contain a placeholder ('xxxxx').")
        
    try:
        client = AsyncMongoClient(mongo_url, serverSelectionTimeoutMS=5000)
        await client.admin.command("ping")
        print("MongoDB Connection: SUCCESS")
    except Exception as e:
        print(f"MongoDB Connection: FAILED - {e}")

if __name__ == "__main__":
    asyncio.run(test())
