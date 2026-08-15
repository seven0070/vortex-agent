#!/usr/bin/env python3
"""
Vortex Agent Backend Runner

This script starts the FastAPI backend server for the Vortex Agent platform.
"""

import os
import sys
from pathlib import Path

# Add the backend directory to Python path
BACKEND_DIR = Path(__file__).parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

if __name__ == "__main__":
    import uvicorn
    
    # Change to backend directory
    os.chdir(BACKEND_DIR)
    
    # Run the FastAPI app
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )