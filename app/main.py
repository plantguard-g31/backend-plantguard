from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import logging

# Import routers
from app.api.v1 import auth, diagnosis, history, admin
 


# Import middleware and handlers
from app.middleware.error_handler import register_error_handlers
from app.middleware.security import rate_limit_middleware
from app.middleware.audit_logger import audit_middleware  

# Import AI model loader (optional: for pre-loading DeiT at startup)
# from app.services.ai_client import load_model

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("plantguard")

# ─────────────────────────────────────────────────────────────
# FASTAPI APPLICATION INSTANCE
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="PlantGuard API",
    version="1.0.0",
    description="Secure backend for real-time plant disease diagnosis with expert-verified treatments",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# ─────────────────────────────────────────────────────────────
# MIDDLEWARE REGISTRATION (Order matters!)
# ─────────────────────────────────────────────────────────────

# 1. CORS: Enable Flutter app connectivity
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  #  Restrict to ["https://your-flutter-app.com"] in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. GZip: Compress responses >500 bytes (60-80% size reduction for low-bandwidth users)
app.add_middleware(GZipMiddleware, minimum_size=500)

# 3. Audit Logger: Log all critical requests (login, diagnose, admin actions)
app.middleware("http")(audit_middleware)  

# 4. Rate Limiting: Prevent DoS attacks (10 requests/60s per authenticated user)
app.middleware("http")(rate_limit_middleware)

# ─────────────────────────────────────────────────────────────
# ROUTER MOUNTING
# ─────────────────────────────────────────────────────────────

# Auth endpoints: /api/v1/auth/register, /login, /refresh, /logout
app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])

# Diagnosis pipeline: /api/v1/diagnose (main feature)
app.include_router(diagnosis.router, prefix="/api/v1", tags=["Diagnosis Pipeline"])

# History endpoint: /api/v1/history (past diagnoses for authenticated user)
app.include_router(history.router, prefix="/api/v1", tags=["History"])

# Admin endpoints: /api/v1/admin/treatments, /audit-logs
app.include_router(admin.router, prefix="/api/v1", tags=["Admin"])

# ─────────────────────────────────────────────────────────────
# ERROR HANDLERS & GLOBAL CONFIG
# ─────────────────────────────────────────────────────────────

# Register bilingual error handler (translates HTTP codes to EN/NE plain language)
register_error_handlers(app)

# ─────────────────────────────────────────────────────────────
# STARTUP EVENTS (Optional: Pre-load AI model)
# ─────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """
    Runs once when server starts.
    Use to pre-load AI model, warm up DB connections, etc.
    """
    logger.info("PlantGuard backend starting...")
    
    # Optional: Pre-load DeiT model to avoid cold-start latency
    # load_model()
    
    logger.info("PlantGuard backend startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Runs once when server shuts down.
    Use to close DB connections, clean up resources, etc.
    """
    logger.info("PlantGuard backend shutting down...")

# ─────────────────────────────────────────────────────────────
# HEALTH CHECK & REDIRECT ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health_check():
    """
    Basic health check for load balancers / monitoring.
    Returns 200 OK if server is running.
    """
    return {"status": "ok", "service": "PlantGuard Backend"}

@app.get("/healthz", tags=["Health"])
def healthz():
    """
    Extended health check (can add DB/AI connectivity checks here).
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "endpoints": ["/docs", "/redoc", "/openapi.json"]
    }

@app.get("/", response_class=RedirectResponse, include_in_schema=False)
def root():
    """
    Redirect root URL to interactive API documentation.
    """
    return "/docs"