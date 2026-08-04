from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import get_settings

settings = get_settings()

# ─────────────────────────────────────────────────────────────
# THE MAGIC SWITCH: SUPABASE SSL DETECTION
# ─────────────────────────────────────────────────────────────
# Supabase requires SSL for remote internet connections. 
# Local PostgreSQL does not. This automatically detects which one you are using.
connect_args = {
    "ssl": "require",
    "statement_cache_size": 0,
}

# ─────────────────────────────────────────────────────────────
# 1. ENGINE: Connection pool to PostgreSQL
# ─────────────────────────────────────────────────────────────
# ✅ FIXED: Replaced NullPool with proper connection pooling
# 
# pool_size=20: Keeps 20 connections ready to use (no creation delay)
# max_overflow=10: Allows 10 more connections under heavy load (total 30 max)
# pool_timeout=30: Wait 30 seconds for a connection before giving up
# pool_recycle=1800: Recycle connections every 30 minutes (prevents stale connections)
# pool_pre_ping=True: Automatically reconnects if DB drops (critical for rural networks)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,              # Set to True later for debugging SQL queries
    pool_pre_ping=True,      # Auto-reconnect on dropped connections
    pool_size=20,            # ✅ NEW: Keep 20 connections ready
    max_overflow=10,         # ✅ NEW: Allow 10 more under heavy load
    pool_timeout=30,         # ✅ NEW: Wait 30s for connection
    pool_recycle=1800,       # ✅ NEW: Recycle every 30 minutes
    connect_args=connect_args # Automatically handles Supabase SSL
)

# ─────────────────────────────────────────────────────────────
# 2. SESSION FACTORY: How we interact with the DB
# ─────────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False   # Prevents "detached instance" errors
)

# ─────────────────────────────────────────────────────────────
# 3. DEPENDENCY: FastAPI will inject this into every endpoint
# ─────────────────────────────────────────────────────────────
async def get_db() -> AsyncSession:
    """
    FastAPI dependency that provides a database session.
    Uses try/finally to ensure session closes even if error occurs.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()  # Save changes if successful
        except Exception:
            await session.rollback()  # Undo changes if error (ACID compliance)
            raise
        finally:
            await session.close()  # Always close the session