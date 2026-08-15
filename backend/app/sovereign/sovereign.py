"""Sovereign – strategic control layer."""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from ..models import SovereignState, SessionLocal


class SovereignEngine:
    """
    Maintains the strategic identity, objectives, priorities, and lifecycle
    state of the Vortex Agent.  It does NOT execute tools directly – it
    emits objectives + constraints that the Orchestration layer consumes.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        # Ensure a singleton row exists
        self._ensure_state()

    def _ensure_state(self) -> None:
        """Create the single SovereignState row if it doesn't exist."""
        state = self.db.query(SovereignState).first()
        if not state:
            state = SovereignState(
                identity="Vortex Agent – autonomous local-first AI platform",
                long_term_objectives=[
                    "Maintain user sovereignty over data and execution",
                    "Provide reliable, auditable autonomous task execution",
                    "Enable controlled self-improvement with rollback safety",
                ],
                current_objectives=[
                    "Bootstrap core orchestration loop",
                    "Validate governance enforcement",
                    "Demonstrate Council → Resolution → Tool pipeline",
                ],
                priorities={"reliability": 1.0, "safety": 1.0, "latency": 0.7},
                system_state={"phase": "bootstrapping"},
                lifecycle_phase="born",
            )
            self.db.add(state)
            self.db.commit()
            self.db.refresh(state)
        self._state = state

    # ------------------------------------------------------------------
    # Read accessors
    # ------------------------------------------------------------------
    def get_identity(self) -> str:
        return self._state.identity

    def get_long_term_objectives(self) -> List[str]:
        return list(self._state.long_term_objectives or [])

    def get_current_objectives(self) -> List[str]:
        return list(self._state.current_objectives or [])

    def get_priorities(self) -> Dict[str, float]:
        return dict(self._state.priorities or {})

    def get_system_state(self) -> Dict[str, Any]:
        return dict(self._state.system_state or {})

    def get_lifecycle_phase(self) -> str:
        return self._state.lifecycle_phase

    # ------------------------------------------------------------------
    # Mutation helpers – used by higher-level control loops
    # ------------------------------------------------------------------
    def set_current_objectives(self, objectives: List[str]) -> None:
        self._state.current_objectives = objectives
        self._state.updated_at = datetime.utcnow()
        self.db.commit()

    def set_priorities(self, priorities: Dict[str, float]) -> None:
        self._state.priorities = priorities
        self._state.updated_at = datetime.utcnow()
        self.db.commit()

    def set_system_state(self, state: Dict[str, Any]) -> None:
        self._state.system_state = state
        self._state.updated_at = datetime.utcnow()
        self.db.commit()

    def advance_lifecycle(self, new_phase: str) -> None:
        valid = ["born", "operational", "canary", "deployed", "monitored", "rollback"]
        if new_phase not in valid:
            raise ValueError(f"Invalid lifecycle phase: {new_phase}")
        self._state.lifecycle_phase = new_phase
        self._state.updated_at = datetime.utcnow()
        self.db.commit()

    # ------------------------------------------------------------------
    # Objective + constraint packaging for Orchestration
    # ------------------------------------------------------------------
    def emit_objective_package(self) -> Dict[str, Any]:
        """
        Produce the payload that Orchestration consumes:
        {
            "objective": str,
            "constraints": dict,
            "priority": float,
            "desired_outcome": str,
        }
        """
        # For now, take the first current objective as the active one
        active_obj = (
            self._state.current_objectives[0]
            if self._state.current_objectives
            else "No active objective"
        )
        return {
            "objective": active_obj,
            "constraints": {
                "lifecycle_phase": self._state.lifecycle_phase,
                "priorities": self._state.priorities,
                "system_state": self._state.system_state,
            },
            "priority": max(self._state.priorities.values()) if self._state.priorities else 1.0,
            "desired_outcome": "Objective completed with governance compliance and audit trail",
        }


# ----------------------------------------------------------------------
# Factory
# ----------------------------------------------------------------------
def SovereignFactory(db: Session) -> SovereignEngine:
    return SovereignEngine(db)