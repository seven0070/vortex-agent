"""Vortex Agent backend smoke tests — runnable in CI without a live LLM.

Covers: settings store, models, governance engine, router wiring.
Run: python -m pytest backend/tests -v  (or: python backend/tests/smoke.py)
"""

import os
import sys
from pathlib import Path

# Ensure backend/ is importable
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("VORTEX_HOME", str(BACKEND / "vortex-data-test"))

import pytest  # noqa: E402


@pytest.fixture()
def db():
    from app.models import Base, SessionLocal, create_engine_from_config
    Base.metadata.create_all(bind=create_engine_from_config())
    s = SessionLocal()
    yield s
    s.close()


def test_settings_defaults():
    from app.vortex.settings import all_settings, get_setting
    s = all_settings()
    assert "llm_base_url" in s
    assert get_setting("llm_model")
    assert isinstance(get_setting("cors_origins"), list)


def test_settings_set_get(tmp_path, monkeypatch):
    from app.vortex import settings as mod
    monkeypatch.setattr(mod, "SETTINGS_FILE", tmp_path / "settings.json")
    mod.set_setting("llm_model", "test-model")
    assert mod.get_setting("llm_model") == "test-model"


def test_chat_models_exist():
    from app.models import ChatSession, ChatMessage
    assert ChatSession.__tablename__ == "chat_sessions"
    assert ChatMessage.__tablename__ == "chat_messages"


def test_governance_engine(db):
    from app.governance.governance import GovernanceEngine
    gov = GovernanceEngine(db)
    # unknown operation -> DENY, and the log insert must not crash (resource NOT NULL)
    decision = gov.is_allowed("self_modification", None, "ci-test")
    assert decision == "DENY"
    # glob matcher works
    m = gov._compile_glob("/home/*/docs/*.md")
    assert m("/home/a/docs/x.md") is not None
    assert m("/tmp/x.md") is None


def test_llm_client_import():
    from app.core.llm_client import chat_stream, chat_once, is_available
    assert callable(chat_stream) and callable(chat_once) and callable(is_available)


def test_routers_wire():
    from app.main import app
    # Authoritative route check: the OpenAPI schema lists every path the app
    # actually serves, regardless of FastAPI's internal router representation
    # (older versions flatten app.routes, newer ones wrap them in _IncludedRouter).
    paths = set(app.openapi()["paths"].keys())
    for expected in (
        "/api/v1/health",
        "/api/v1/settings",
        "/api/v1/settings/improve",
        "/api/v1/evolution/candidates",
        "/api/v1/governance/logs",
        "/api/v1/benchmarks",
    ):
        assert expected in paths, f"missing route {expected}"


def test_evolution_candidate(db):
    from app.evolution.evolution_engine import EvolutionEngineFactory
    from app.governance.governance import GovernanceEngine
    engine = EvolutionEngineFactory(db)
    c = engine.propose_improvement("ci smoke test")
    assert c.candidate_id
    assert c.generation_id
