from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import get_settings

settings = get_settings()

# ─────────────────────────────────────────────────────────────
# THE MAGIC SWITCH: SUPABASE SSL DETECTION
# ─────────────────────────────────────────────────────────────
# Supabase requires SSL for remote internet connections. 
# Local PostgreSQL does not. This automatically detects which one you are using.
connect_args = {}
if "supabase" in settings.DATABASE_URL:
    connect_args["ssl"] = "require"

# ─────────────────────────────────────────────────────────────
# 1. ENGINE: Connection pool to PostgreSQL
# ─────────────────────────────────────────────────────────────
# pool_pre_ping=True: Automatically reconnects if DB drops (critical for rural networks)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,              # Set to True later for debugging SQL queries
    pool_pre_ping=True,      # Auto-reconnect on dropped connections
    poolclass=NullPool,      # Simpler for dev; use QueuePool in production
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