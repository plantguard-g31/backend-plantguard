from fastapi import Request
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import AsyncSessionLocal
from app.db.models import AuditLog, User
from app.core.security import decode_token
import uuid

logger = logging.getLogger("plantguard.audit")

async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    
    # Log only critical endpoints
    if request.url.path in ["/api/v1/auth/login", "/api/v1/diagnose", "/api/v1/admin"]:
        try:
            auth_header = request.headers.get("Authorization", "")
            user_id = None
            if auth_header.startswith("Bearer "):
                payload = decode_token(auth_header.split(" ")[1])
                user_id = payload.get("sub")
        except:
            pass
            
        async with AsyncSessionLocal() as db:
            log_entry = AuditLog(
                user_id=user_id,
                action=request.method,
                endpoint=request.url.path,
                http_status=response.status_code,
                ip_address=request.client.host,
                detail=f"User-Agent: {request.headers.get('User-Agent', 'Unknown')}"
            )
            db.add(log_entry)
            await db.commit()
            
    return response