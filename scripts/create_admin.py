import asyncio
import os
import uuid
from datetime import datetime  # <-- ADDED: To get the current time
from dotenv import load_dotenv
import asyncpg
import bcrypt

# Load environment variables from .env
load_dotenv()

SYNC_DATABASE_URL = os.getenv("SYNC_DATABASE_URL")

def hash_password(plain_password: str) -> str:
    """Hash a password using bcrypt (Matches app/core/security.py)"""
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed_bytes.decode("utf-8")

async def create_super_admin():
    if not SYNC_DATABASE_URL:
        print("❌ Error: SYNC_DATABASE_URL not found in .env file.")
        return

    print("🛡️ PlantGuard Super Admin Bootstrap Script")
    print("------------------------------------------")
    
    # 1. Get credentials from terminal input
    name = input("Enter Admin Name: ")
    email = input("Enter Admin Email: ")
    password = input("Enter Admin Password: ")
    
    hashed_pw = hash_password(password)
    
    # 2. Configure SSL for Supabase
    connect_kwargs = {}
    if "supabase" in SYNC_DATABASE_URL:
        connect_kwargs["ssl"] = "require"

    try:
        # 3. Connect to Database
        conn = await asyncpg.connect(SYNC_DATABASE_URL, **connect_kwargs)
        
        # 4. Check if this email already exists as a farmer
        exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM users WHERE email=$1)", email)
        
        if exists:
            # UPGRADE PATH: If you already registered as a farmer, upgrade to Super Admin
            await conn.execute("""
                UPDATE users 
                SET role = 'admin', is_super_admin = TRUE 
                WHERE email = $1
            """, email)
            print(f"\n✅ User '{email}' successfully UPGRADED to SUPER ADMIN.")
        else:
            # CREATION PATH: Create a brand new Super Admin account
            admin_id = str(uuid.uuid4())
            now = datetime.utcnow()  # <-- FIX: Get current UTC time
            
            # FIX: Added created_at and updated_at to the INSERT statement
            await conn.execute("""
                INSERT INTO users (
                    id, name, email, password_hash, role, is_super_admin, 
                    language_pref, is_active, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, 'admin', TRUE, 'en', TRUE, $5, $5)
            """, admin_id, name, email, hashed_pw, now)
            
            print(f"\n✅ Super Admin '{name}' ({email}) CREATED successfully!")
            
        print("\n🔑 You can now log in to the Flutter app or Swagger UI with these credentials.")
        print("👑 Remember: You are the ONLY Super Admin. Regular admins cannot create other admins.")
        
    except Exception as e:
        print(f"\n❌ Database Error: {e}")
    finally:
        if 'conn' in locals():
            await conn.close()

if __name__ == "__main__":
    asyncio.run(create_super_admin())