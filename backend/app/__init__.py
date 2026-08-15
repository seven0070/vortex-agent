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
# CORS – allow the Tauri UI (running on localhost:7777 by default)
# ----------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:7777"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
# Include API routers
# ----------------------------------------------------------------------
from .api.v1 import routers

app.include_router(routers.api_router, prefix="/api/v1")

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
    # Lazy load heavy components here if needed
    pass

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Vortex Agent backend shutting down...")
    pass

# ----------------------------------------------------------------------
# Run with Uvicorn when executed as script
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)