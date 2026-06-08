from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import get_settings

settings = get_settings()

# 1. Engine: Connection pool to PostgreSQL
# pool_pre_ping=True: Automatically reconnects if DB drops (critical for rural networks)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,              # Set to True later for debugging SQL queries
    pool_pre_ping=True,      # Auto-reconnect on dropped connections
    poolclass=NullPool       # Simpler for dev; use QueuePool in production
)

# 2. Session Factory: How we interact with the DB
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False   # Prevents "detached instance" errors
)

# 3. Dependency: FastAPI will inject this into every endpoint
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