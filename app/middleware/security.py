import time
import logging
from typing import Dict
from fastapi import HTTPException, status, UploadFile, Header, Request
from fastapi.responses import JSONResponse
from app.core.config import get_settings
from app.core.security import decode_token

settings = get_settings()
logger = logging.getLogger("plantguard")

# In-memory rate limit store: {user_id: {"tokens": int, "reset_time": float}}
_rate_limits: Dict[str, dict] = {}

# Magic bytes signatures (CWE-434 prevention)
MAGIC_BYTES = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}

def check_rate_limit(user_id: str) -> bool:
    """
    Internal function: checks if user has tokens remaining.
    Returns True if allowed, False if rate limited.
    """
    now = time.time()
    user_data = _rate_limits.get(user_id)
    
    # Reset bucket if window expired
    if not user_data or now > user_data["reset_time"]:
        _rate_limits[user_id] = {
            "tokens": settings.RATE_LIMIT_TOKENS,
            "reset_time": now + settings.RATE_LIMIT_WINDOW
        }
        user_data = _rate_limits[user_id]
    
    # Check tokens
    if user_data["tokens"] <= 0:
        return False
    
    user_data["tokens"] -= 1
    return True

async def rate_limit_middleware(request: Request, call_next):
    """
    FastAPI HTTP middleware that enforces rate limiting on ALL requests.
    Extracts user ID from JWT in Authorization header.
    """
    # Skip rate limiting for public endpoints (register, health, docs)
    if request.url.path in ["/docs", "/openapi.json", "/health", "/api/v1/auth/register"]:
        return await call_next(request)
    
    # Try to extract user ID from JWT
    auth_header = request.headers.get("Authorization", "")
    user_id = None
    
    if auth_header.startswith("Bearer "):
        try:
            token = auth_header.replace("Bearer ", "")
            payload = decode_token(token)
            user_id = payload.get("sub")
        except Exception:
            # Invalid token - let auth dependency handle it later
            pass
    
    # If we have a user ID, enforce rate limit
    if user_id:
        if not check_rate_limit(user_id):
            logger.warning(f"Rate limit exceeded for user {user_id}")
            # Return bilingual error based on query param
            lang = request.query_params.get("lang", "en")
            detail = {
                "en": "Too many requests. Please wait 60 seconds.",
                "ne": "धेरै अनुरोधहरू। कृपया ६० सेकेन्ड कुर्नुहोस्।"
            }.get(lang, "Too many requests. Please wait 60 seconds.")
            
            return JSONResponse(
                status_code=429,
                content={"detail": detail, "status": "error", "code": 429}
            )
    
    # Continue to next middleware/endpoint
    return await call_next(request)

async def validate_upload_file(file: UploadFile) -> dict:
    """
    Checks file size and magic bytes before any processing.
    Prevents memory exhaustion and malicious file uploads.
    """
    # 1. Payload Size Check
    file.file.seek(0, 2)
    size_bytes = file.file.tell()
    file.file.seek(0)
    
    if size_bytes > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        logger.warning(f"File too large: {size_bytes} bytes")
        raise HTTPException(status_code=413, detail="file_too_large")
    
    # 2. Magic Byte Validation
    magic = await file.read(8)
    await file.seek(0)
    
    if not any(magic.startswith(sig) for sig in MAGIC_BYTES.values()):
        logger.warning("Invalid magic bytes detected")
        raise HTTPException(status_code=415, detail="invalid_file_format")
    
    return {"size_bytes": size_bytes, "valid": True}