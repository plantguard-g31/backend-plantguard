from fastapi import Request
import logging
from app.db.base import AsyncSessionLocal
from app.db.models import AuditLog
from app.core.security import decode_token

logger = logging.getLogger("plantguard.audit")

async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    
    # Log only critical endpoints to avoid spamming the DB
    critical_paths = ["/api/v1/auth/login", "/api/v1/diagnose", "/api/v1/admin"]
    if any(path in request.url.path for path in critical_paths):
        try:
            # Extract user_id from JWT if present
            auth_header = request.headers.get("Authorization", "")
            user_id = None
            if auth_header.startswith("Bearer "):
                payload = decode_token(auth_header.split(" ")[1])
                user_id = payload.get("sub")
                
            # Determine event type based on endpoint
            if "/diagnose" in request.url.path:
                event_type = "diagnose"
            elif "/login" in request.url.path:
                event_type = "login" if response.status_code == 200 else "failed_login"
            else:
                event_type = "admin_action"

            async with AsyncSessionLocal() as db:
                log_entry = AuditLog(
                    user_id=user_id,
                    event_type=event_type, # Matches new SRS v3.1 column
                    endpoint=request.url.path,
                    ip_address=request.client.host,
                    user_agent=request.headers.get("User-Agent", "Unknown"),
                    additional_data={ # Matches new SRS v3.1 JSONB column
                        "http_status": response.status_code,
                        "method": request.method
                    }
                )
                db.add(log_entry)
                await db.commit()
        except Exception as e:
            # Never let audit logging crash the main application
            logger.error(f"Audit logging failed: {e}")
            
    return response