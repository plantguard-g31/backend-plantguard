import sys
import os
from pathlib import Path
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# Load environment variables from .env file (CRITICAL for Supabase switching)
load_dotenv()

# 1. Force project root into Python path (guarantees imports work)
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 2. Import your SQLAlchemy Base
try:
    from app.db.models import Base
    target_metadata = Base.metadata
    print("✅ Successfully imported Base.metadata from app.db.models")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# 3. Alembic config setup
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 4. Offline mode (for generating SQL scripts without DB)
def run_migrations_offline() -> None:
    # Use SYNC_DATABASE_URL from .env if available, else fallback to alembic.ini
    url = os.getenv("SYNC_DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

# 5. Online mode (connects to live DB)
def run_migrations_online() -> None:
    # Read the SYNC URL from .env, fallback to alembic.ini if missing
    db_url = os.getenv("SYNC_DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = db_url # Override the URL with .env variable
    
    # Helpful log to verify which database Alembic is talking to
    if "supabase" in db_url:
        print("🔗 Alembic connecting to: Supabase Cloud Database")
    else:
        print("🔗 Alembic connecting to: Local PostgreSQL Database")

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata  # ← CRITICAL: This must be here
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()