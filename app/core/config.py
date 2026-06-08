from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:ritikbt@localhost:5432/plantguard"
    
    # Security
    JWT_SECRET: str = "vlHvwYRPDbN4CqVX-lBYFMT8_O1KszPYxB0SFH_zR48"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30
    
    # Rate Limiting & Uploads
    RATE_LIMIT_TOKENS: int = 10
    RATE_LIMIT_WINDOW: int = 60  # seconds
    MAX_FILE_SIZE_MB: int = 5

    # Prevent accidental loading of wrong env files
    model_config = {"env_file": ".env", "extra": "ignore"}

@lru_cache()
def get_settings() -> Settings:
    return Settings()