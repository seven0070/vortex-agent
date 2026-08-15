"""
Runtime settings store — persists configurable Vortex Agent settings to
vortex-data/settings.json. Env vars always take precedence over stored values.

Keys:
    llm_base_url   OpenAI-compatible LLM endpoint (default: hermes proxy)
    llm_api_key    Bearer token for the LLM endpoint
    llm_model      Model slug (default: qwen/qwen3.8-27b)
    cors_origins   List of allowed browser origins (frontend dev + tauri)
"""

import json
import os
from pathlib import Path

from .config import DATA_DIR

SETTINGS_FILE = Path(DATA_DIR) / "settings.json"

DEFAULTS = {
    "llm_base_url": "http://localhost:8645/v1",
    "llm_api_key": "local",
    "llm_model": "qwen/qwen3.8-27b",
    "cors_origins": ["http://localhost:7777", "http://localhost:5173", "tauri://localhost"],
}

# env var -> settings key
_ENV_MAP = {
    "VORTEX_LLM_BASE_URL": "llm_base_url",
    "VORTEX_LLM_API_KEY": "llm_api_key",
    "VORTEX_LLM_MODEL": "llm_model",
}


def _load() -> dict:
    if SETTINGS_FILE.exists():
        try:
            stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                return stored
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save(data: dict) -> None:
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_setting(key: str, default=None):
    """Read a setting: env var wins, then stored value, then default."""
    env_key = next((e for e, k in _ENV_MAP.items() if k == key), None)
    if env_key and os.getenv(env_key):
        return os.getenv(env_key)
    return _load().get(key, DEFAULTS.get(key, default))


def set_setting(key: str, value) -> None:
    """Persist a setting (env vars still take precedence at read time)."""
    if key not in DEFAULTS and key != "cors_origins":
        raise KeyError(f"Unknown setting '{key}'. Known: {list(DEFAULTS.keys())}")
    data = _load()
    data[key] = value
    _save(data)


def all_settings() -> dict:
    """Merged view: defaults + stored + env overrides (effective values)."""
    merged = dict(DEFAULTS)
    merged.update(_load())
    for env, key in _ENV_MAP.items():
        if os.getenv(env):
            merged[key] = os.getenv(env)
    return merged
