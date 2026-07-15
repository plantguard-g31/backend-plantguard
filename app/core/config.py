from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str 
    SYNC_DATABASE_URL: str 

    # Security
    JWT_SECRET: str 
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30
    
    # Rate Limiting & Uploads
    RATE_LIMIT_TOKENS: int = 10
    RATE_LIMIT_WINDOW: int = 60  # seconds
    MAX_FILE_SIZE_MB: int = 5

    # Email Service (Password Reset)
    RESEND_API_KEY: str 
    OTP_EXPIRE_MINUTES: int = 15
    

    # Supabase for User Profile
    SUPABASE_URL: str 
    SUPABASE_KEY: str 

    # Prevent accidental loading of wrong env files
    model_config = {"env_file": ".env", "extra": "ignore"}

@lru_cache()
def get_settings() -> Settings:
    return Settings()