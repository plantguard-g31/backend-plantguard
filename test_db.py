import asyncio
import os
from dotenv import load_dotenv
import asyncpg

# 1. Load environment variables from .env
load_dotenv()

async def test_database():
    print("\n--- 🌿 PLANTGUARD DATABASE CONNECTION TEST ---\n")
    
    # 2. Get the URL (Prefer SYNC_DATABASE_URL for asyncpg, fallback to DATABASE_URL)
    db_url = os.getenv("SYNC_DATABASE_URL") or os.getenv("DATABASE_URL")
    
    if not db_url:
        print("❌ CRITICAL ERROR: Neither SYNC_DATABASE_URL nor DATABASE_URL is set in your .env file!")
        return

    # Hide password in console for security
    safe_url = db_url.split("@")[0] + "@******" + db_url.split("@")[1]
    print(f"✅ URL Loaded: {safe_url}")
    
    try:
        print("⏳ Attempting to connect to Supabase (requires SSL)...")
        
        # asyncpg needs standard 'postgresql://', not 'postgresql+asyncpg://'
        clean_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Connect with SSL required (Mandatory for Supabase)
        conn = await asyncpg.connect(clean_url, ssl="require")
        print("✅ SUCCESS: Connected to the database!\n")
        
        # Run a simple query to verify it's alive
        version = await conn.fetchval("SELECT version();")
        print(f"📦 Database Engine: {version.split(',')[0]}")
        
        # Check if your tables exist
        tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public';")
        print(f"\n📂 Found {len(tables)} tables in 'public' schema:")
        for t in tables:
            print(f"   ✅ {t['tablename']}")
            
        await conn.close()
        print("\n🎉 ALL TESTS PASSED! Your backend is ready to connect to Supabase.")

    except asyncpg.InvalidPasswordError:
        print("\n❌ AUTHENTICATION FAILED!")
        print("👉 Your password in the .env file is incorrect.")
        print("👉 If your password has special characters (like @, #), they MUST be URL-encoded in the .env file.")
        
    except asyncpg.CannotConnectNowError:
        print("\n❌ CONNECTION REFUSED!")
        print("👉 Your Supabase project might be PAUSED. Go to supabase.com and click 'Resume Project'.")
        print("👉 Check your internet connection.")
        
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        print("👉 Double-check your .env file for typos.")

# ⚠️ THIS IS THE CRITICAL LINE THAT WAS LIKELY MISSING:
if __name__ == "__main__":
    asyncio.run(test_database())