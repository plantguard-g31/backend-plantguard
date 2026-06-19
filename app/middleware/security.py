import time
import logging
from typing import Dict
from fastapi import HTTPException, status, UploadFile, Request
from fastapi.responses import JSONResponse
from app.core.config import get_settings
from app.core.security import decode_token

settings = get_settings()
logger = logging.getLogger("plantguard")

# In-memory rate limit store
_rate_limits: Dict[str, dict] = {}

# Magic bytes signatures (CWE-434 prevention)
MAGIC_BYTES = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}

def check_rate_limit(user_id: str) -> bool:
    now = time.time()
    user_data = _rate_limits.get(user_id)
    
    if not user_data or now > user_data["reset_time"]:
        _rate_limits[user_id] = {
            "tokens": settings.RATE_LIMIT_TOKENS,
            "reset_time": now + settings.RATE_LIMIT_WINDOW
        }
        user_data = _rate_limits[user_id]
    
    if user_data["tokens"] <= 0:
        return False
    
    user_data["tokens"] -= 1
    return True

async def rate_limit_middleware(request: Request, call_next):
    # Skip rate limiting for public endpoints
    if request.url.path in ["/docs", "/openapi.json", "/api/v1/health", "/api/v1/auth/register", "/api/v1/auth/login"]:
        return await call_next(request)
    
    auth_header = request.headers.get("Authorization", "")
    user_id = None
    
    if auth_header.startswith("Bearer "):
        try:
            token = auth_header.replace("Bearer ", "")
            payload = decode_token(token)
            user_id = payload.get("sub")
        except Exception:
            pass
    
    if user_id:
        if not check_rate_limit(user_id):
            logger.warning(f"Rate limit exceeded for user {user_id}")
            # SRS FR-07: Rate Limit -> 429 with Retry-After header
            response = JSONResponse(
                status_code=429,
                content={"error_code": "429", "message_en": "Too many requests. Please wait 60 seconds.", "message_ne": "धेरै अनुरोधहरू। कृपया ६० सेकेन्ड कुर्नुहोस्।"}
            )
            response.headers["Retry-After"] = "60"
            return response
    
    return await call_next(request)

async def validate_upload_file(file: UploadFile) -> dict:
    # 1. Payload Size Check (SRS FR-06: >5MB -> 413)
    file.file.seek(0, 2)
    size_bytes = file.file.tell()
    file.file.seek(0)
    
    if size_bytes > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        logger.warning(f"File too large: {size_bytes} bytes")
        raise HTTPException(status_code=413, detail="file_too_large")
    
    # 2. Magic Byte Validation (SRS FR-05: Invalid format -> 415)
    magic = await file.read(8)
    await file.seek(0)
    
    if not any(magic.startswith(sig) for sig in MAGIC_BYTES.values()):
        logger.warning("Invalid magic bytes detected")
        raise HTTPException(status_code=415, detail="invalid_magic_bytes")
    
    return {"size_bytes": size_bytes, "valid": True}