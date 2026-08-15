# Backend configuration
import os
import sys
from pathlib import Path

# Resolve paths relative to this file (backend/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _default_data_dir() -> Path:
    """Platform-appropriate user-data directory (never the install dir).

    Windows: %APPDATA%/Vortex          (e.g. C:/Users/<u>/AppData/Roaming/Vortex)
    macOS:   ~/Library/Application Support/Vortex
    Linux:   $XDG_DATA_HOME or ~/.local/share/Vortex
    """
    if sys.platform == "win32":
        base = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "Vortex"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Vortex"
    # Linux / other POSIX
    base = os.getenv("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "Vortex"


def _resolve_data_dir() -> Path:
    """VORTEX_HOME env wins; fall back to platform user-data dir.

    Dev override: set VORTEX_HOME=backend/vortex-data to keep data in-repo
    during development (the smoke tests do exactly this).
    """
    env = os.getenv("VORTEX_HOME")
    if env:
        return Path(env)
    return _default_data_dir()


# Data directory for persistence (user-data dir by default)
DATA_DIR = _resolve_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database path
SQLITE_URL = f"sqlite:///{DATA_DIR / 'vortex.db'}"

# Sub-directories for separation of concerns
CONFIG_DIR = DATA_DIR / "config"
MEMORY_DIR = DATA_DIR / "memory"
LOG_DIR = DATA_DIR / "logs"
MODELS_DIR = DATA_DIR / "models"

for _d in (CONFIG_DIR, MEMORY_DIR, LOG_DIR, MODELS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'formatter': 'standard',
            'stream': 'ext://sys.stdout',
        },
        'file': {
            'formatter': 'standard',
            'path': str(LOG_DIR / 'vortex.log'),
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 3,
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['default', 'file'],
    },
}
