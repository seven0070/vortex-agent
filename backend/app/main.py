"""Vortex Agent backend entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .vortex.config import LOGGING_CONFIG
import logging
import sys

# ----------------------------------------------------------------------
# Logging setup
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format=LOGGING_CONFIG['formatters']['standard']['format'],
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGGING_CONFIG['handlers']['file']['path'])
    ]
)
logger = logging.getLogger('vortex')

# ----------------------------------------------------------------------
# Create FastAPI app
# ----------------------------------------------------------------------
app = FastAPI(
    title="Vortex Agent API",
    version="1.0.0",
    description="Local-first autonomous AI agent platform",
)

# ----------------------------------------------------------------------
# CORS – allow frontend origins (configurable via vortex-data/settings.json)
# ----------------------------------------------------------------------
from .vortex.settings import get_setting

_cors_origins = get_setting("cors_origins") or ["http://localhost:7777"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if isinstance(_cors_origins, list) else [_cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
# Include API routers
# ----------------------------------------------------------------------
from .api.v1 import routers

# routers.api_router already declares prefix="/api/v1" in routers.py;
# do NOT add a second prefix here or paths become /api/v1/api/v1/...
app.include_router(routers.api_router)

# ----------------------------------------------------------------------
# Root endpoint (health check)
# ----------------------------------------------------------------------
@app.get("/", tags=["health"])
def read_root():
    return {"status": "ok", "message": "Vortex Agent backend is running"}

# ----------------------------------------------------------------------
# Startup/shutdown events
# ----------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    logger.info("Vortex Agent backend starting up...")
    # Ensure all tables (incl. chat_sessions / chat_messages) exist
    from .models import Base, create_engine_from_config
    Base.metadata.create_all(bind=create_engine_from_config())
    logger.info("Database tables ensured.")
    # Lazy load heavy components here if needed
    pass

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Vortex Agent backend shutting down...")
    pass