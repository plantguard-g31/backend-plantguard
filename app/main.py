from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from datetime import datetime, timezone
import logging

# Import routers
from app.api.v1 import auth, diagnosis, history, admin, analytics, user

# Import middleware and handlers
from app.middleware.error_handler import register_error_handlers
from app.middleware.security import rate_limit_middleware
from app.middleware.audit_logger import audit_middleware  

# Import AI model loader
from app.services.ai_client import _load_model

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
    version="3.1", # Updated to match SRS v3.1
    description="Secure backend for real-time plant disease diagnosis with expert-verified treatments",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# ─────────────────────────────────────────────────────────────
# MIDDLEWARE REGISTRATION (Order matters!)
# ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React frontend
        "http://localhost:8080"  
        "http://localhost:8000"
    ], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.middleware("http")(audit_middleware)  
app.middleware("http")(rate_limit_middleware)

# ─────────────────────────────────────────────────────────────
# ROUTER MOUNTING
# ─────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(diagnosis.router, prefix="/api/v1", tags=["Diagnosis Pipeline"])
app.include_router(history.router, prefix="/api/v1", tags=["History"])
app.include_router(admin.router, prefix="/api/v1", tags=["Admin"])
app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"])
app.include_router(user.router, prefix="/api/v1")

# ─────────────────────────────────────────────────────────────
# ERROR HANDLERS & GLOBAL CONFIG
# ─────────────────────────────────────────────────────────────
register_error_handlers(app)

# ─────────────────────────────────────────────────────────────
# STARTUP EVENTS
# ─────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    logger.info("PlantGuard starting...")
    # Pre-load DeiT-Tiny model to avoid cold-start latency on first request 
    _load_model()
    logger.info("PlantGuard startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("PlantGuard shutting down...")

# ─────────────────────────────────────────────────────────────
# HEALTH CHECK & REDIRECT ENDPOINTS
# ─────────────────────────────────────────────────────────────
@app.get("/api/v1/health", tags=["Health"])
def health_check():
   
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "3.1"
    }

@app.get("/", response_class=RedirectResponse, include_in_schema=False)
def root():
    return "/docs"