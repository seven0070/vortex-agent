# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — bundle the Vortex FastAPI backend into a single exe.

Build (Windows):
    cd backend
    pip install pyinstaller
    pyinstaller vortex-backend.spec

Output: dist/vortex-backend.exe
        (Tauri sidecar expects it at frontend/src-tauri/binaries/vortex-backend.exe)

The exe serves the API on 0.0.0.0:8000 with --host/--port passthrough:
    vortex-backend.exe [--host 0.0.0.0] [--port 8000]
"""

import os
from pathlib import Path

ROOT = Path(SPECPATH)  # backend/ (where the spec lives)

a = Analysis(
    ["backend_entry.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # package data if any (e.g. governance policy JSON) would go here
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.lifespan",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        "sqlalchemy.dialects.sqlite",
        "app.api.v1.routers",
        "app.api.v1.settings",
        "app.core.llm_client",
        "app.core.memory_system",
        "app.core.orchestration",
        "app.core.tools",
        "app.council.council",
        "app.governance.governance",
        "app.sovereign.sovereign",
        "app.knowledge.graph",
        "app.evolution.evolution_engine",
        "app.observability.trace",
        "app.tools.tool_registry",
        "app.vortex.config",
        "app.vortex.settings",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="vortex-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # console window so logs are visible in dev; False for release
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
