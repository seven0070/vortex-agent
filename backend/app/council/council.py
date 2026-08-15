"""Council – multi‑agent deliberation layer."""

from __future__ import annotations
from typing import List, Dict, Any
from uuid import uuid4

from ..models import SessionLocal
from ..core.memory_system import add_memory, recall
from ..sovereign.sovereign import SovereignEngine
from ..knowledge.graph import KnowledgeGraph

# ----------------------------------------------------------------------
# Simple agent role definitions – in a real app these would be separate agents,
# but for this scaffold we keep them as strings used for weighting.
# ----------------------------------------------------------------------
_ROLE_WEIGHTS: Dict[str, float] = {
    "researcher": 1.0,
    "planner": 1.0,
    "engineer": 1.0,
    "critic": 1.0,
    "security": 1.2,
    "strategist": 1.1,
    "verifier": 1.0,
}


def _weight_for(role: str) -> float:
    """Return the decision‑weight for a given role."""
    return _ROLE_WEIGHTS.get(role.lower(), 1.0)


class Council:
    """
    Represents the Council layer.  It aggregates proposals from individual
    specialist agents (researcher, planner, engineer, …) and produces a
    weighted, evidential synthesis that downstream layers consume.
    """

    def __init__(
        self,
        sovereign: SovereignEngine,
        knowledge_graph: "KnowledgeGraph",  # noqa: F401 – forward reference; concrete class imported lazily
    ) -> None:
        self.sovereign = sovereign
        self.kg = knowledge_graph

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def propose(self, task_description: str, agent_id: str) -> Dict[str, Any]:
        """
        Run a lightweight “deliberation” to produce a candidate plan.

        Returns
        -------
        dict
            {
                "plan": str,          # high‑level candidate solution
                "confidence": float, # 0‑1 weighted confidence estimate
                "evidence": List[str] # list of source memories or knowledge nodes
            }
        """
        # 1️⃣ Retrieve relevant knowledge for the task
        relevant_memories = recall(
            user_id="admin",  # placeholder – in a real impl use caller's user_id
            query=task_description,
            limit=5,
        )
        evidence_texts = [mem.content for mem in relevant_memories]

        # 2️⃣ Simulate generation of candidate plans by “role agents”
        #     (In a full system each role would run its own LLM/agent.)
        candidate_plans = self._generate_candidate_plans(task_description)

        # 3️⃣ Score each plan based on weighted role support
        scored_plans = []
        for plan in candidate_plans:
            # Rough heuristic: count how many role‑keywords appear in the plan
            scores = {}
            for role, weight in _ROLE_WEIGHTS.items():
                if role in plan.lower():
                    scores[role] = weight
            # Weighted sum of matched roles
            weighted_score = sum(scores.values())
            # Map to 0‑1 confidence range
            normalized_confidence = min(weighted_score / 5.0, 1.0)
            scored_plans.append(
                {
                    "plan": plan,
                    "confidence": normalized_confidence,
                    "evidence": evidence_texts,
                }
            )

        # 4️⃣ Pick the highest‑scoring plan
        best = max(scored_plans, key=lambda x: x["confidence"])
        # Persist the proposal for auditability
        add_memory(
            user_id="admin",
            content=f"Council proposal [{best['plan'][:60]}...] confidence={best['confidence']:.2f}",
            metadata={"evidence": best["evidence"][:3]},
        )
        return {
            "plan": best["plan"],
            "confidence": best["confidence"],
            "evidence": best["evidence"],
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _generate_candidate_plans(self, task_description: str) -> List[str]:
        """
        Produce a handful of synthetic candidate plans.
        In a real system each specialist agent would output a plan string.
        """
        # Deterministic placeholder – returns three generic scaffolds.
        return [
            f"Break the task into phases: 1) analysis, 2) design, 3) implementation, 4) testing",
            f"Delegate sub‑tasks to specialized agents: researcher, planner, engineer",
            f"Build a prototype, measure latency, iterate based on feedback",
        ]