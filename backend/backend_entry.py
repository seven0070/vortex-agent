#!/usr/bin/env python3
"""PyInstaller entry point — starts the Vortex backend with CLI passthrough.

Usage:
    vortex-backend.exe [--host 0.0.0.0] [--port 8000]
"""

import argparse
import os
import sys

# Make bundled `app` package importable regardless of CWD
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def main() -> int:
    parser = argparse.ArgumentParser(description="Vortex Agent backend server")
    parser.add_argument("--host", default=os.getenv("VORTEX_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("VORTEX_PORT", "8000")))
    parser.add_argument("--no-reload", action="store_true", help="disable auto-reload (release)")
    args = parser.parse_args()

    # Import the ASGI app DIRECTLY (not via string) so PyInstaller's static
    # analysis follows the full import graph and bundles every module.
    from app.main import app  # noqa: E402

    import uvicorn

    uvicorn.run(
        app,  # app object, not "app.main:app" string
        host=args.host,
        port=args.port,
        reload=False,  # never reload in a frozen bundle
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
