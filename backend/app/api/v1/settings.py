"""
Settings + Improve endpoints.

Settings: GET/PUT runtime config (llm endpoint, model, cors) persisted in
          vortex-data/settings.json via vortex.settings.
Improve:  self-audit endpoint that reports health + proposes improvements
          through the EvolutionEngine.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...models import SessionLocal, EvolutionCandidate
from ...vortex.settings import all_settings, get_setting, set_setting
from ...governance.governance import GovernanceEngine
from ...evolution.evolution_engine import EvolutionEngineFactory

settings_router = APIRouter(prefix="/settings", tags=["Settings"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@settings_router.get("")
def settings_get():
    """Return effective settings (defaults + stored + env overrides)."""
    return {"settings": all_settings()}


@settings_router.put("")
def settings_put(request: Dict[str, Any]):
    """Persist one or more settings. Keys validated against known set."""
    errors = []
    for key, value in request.items():
        try:
            set_setting(key, value)
        except KeyError as e:
            errors.append(str(e))
    if errors:
        raise HTTPException(400, "; ".join(errors))
    return {"ok": True, "settings": all_settings()}


@settings_router.get("/health")
def settings_health():
    """LLM connectivity + config summary."""
    from ...core.llm_client import is_available
    return {
        "llm_configured": bool(get_setting("llm_base_url")),
        "llm_reachable": is_available(),
        "model": get_setting("llm_model"),
        "base_url": get_setting("llm_base_url"),
    }


@settings_router.post("/improve")
def settings_improve(request: Dict[str, Any], db: Session = Depends(get_db)):
    """Audit + propose improvements through the EvolutionEngine.

    Body (optional):
        {"hypothesis": "text"} — custom improvement idea
    Returns: audit summary + proposed candidate.
    """
    gov = GovernanceEngine(db)
    engine = EvolutionEngineFactory(db)
    from ...core.llm_client import is_available

    # 1. Audit
    audit = {
        "llm_reachable": is_available(),
        "model": get_setting("llm_model"),
        "base_url": get_setting("llm_base_url"),
        "governance_risk_level": gov.risk_level if hasattr(gov, "risk_level") else "unknown",
        "evolution_candidates": db.query(EvolutionCandidate).count(),
    }

    # 2. Propose
    hypothesis = request.get("hypothesis") or (
        "Self-improvement audit: LLM reachable=%s, model=%s"
        % (audit["llm_reachable"], audit["model"])
    )
    candidate = engine.propose_improvement(hypothesis)

    return {
        "audit": audit,
        "proposed": {
            "candidate_id": candidate.candidate_id,
            "generation_id": candidate.generation_id,
            "hypothesis": candidate.hypothesis,
            "decision": candidate.decision,
        },
    }
