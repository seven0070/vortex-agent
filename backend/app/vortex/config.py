# Backend configuration
import os
from pathlib import Path

# Resolve paths relative to this file
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/

# Data directory for persistence
DATA_DIR = os.getenv('VORTEX_HOME', str(BASE_DIR / 'vortex-data'))
DATA_DIR = Path(DATA_DIR)

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database path
SQLITE_URL = f"sqlite:///{DATA_DIR / 'vortex.db'}"

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
            'path': str(DATA_DIR / 'vortex.log'),
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 3,
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['default', 'file'],
    },
}