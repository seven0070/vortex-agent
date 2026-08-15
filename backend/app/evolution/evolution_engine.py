"""Evolution Engine – controlled self‑improvement and candidate lifecycle."""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from uuid import uuid4
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import json

from sqlalchemy.orm import Session
from ..models import EvolutionCandidate, BenchmarkRun, SessionLocal
from ..governance.governance import GovernanceEngine


class EvolutionEngine:
    """
    Implements the Level‑2 Evolution pipeline:
      1. Observe weakness / generate hypothesis
      2. Create isolated candidate workspace
      3. Apply patch / code change
      4. Install deps & run tests
      5. Run benchmarks
      6. Security analysis
      7. Governance gate
      8. Canary deployment
      9. Monitor & promote / rollback
    """

    def __init__(self, db: Session, governance: GovernanceEngine) -> None:
        self.db = db
        self.governance = governance
        self.workspace_root = Path("/tmp/vortex_evolution")  # isolated root
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API – called by Orchestration on failure or scheduled
    # ------------------------------------------------------------------
    def handle_failure(self, task_id: str, error: str) -> None:
        """
        Entry point when a task fails.  Generates a hypothesis and starts
        the candidate generation process.
        """
        hypothesis = self._generate_hypothesis(task_id, error)
        self._spawn_candidate(hypothesis)

    def propose_improvement(self, hypothesis: str) -> EvolutionCandidate:
        """Manual / scheduled entry point for proactive improvements."""
        return self._spawn_candidate(hypothesis)

    # ------------------------------------------------------------------
    # Internal pipeline steps
    # ------------------------------------------------------------------
    def _generate_hypothesis(self, task_id: str, error: str) -> str:
        """Very naive hypothesis generator – replace with LLM in production."""
        return f"Task {task_id} failed with '{error}'. Hypothesis: add retry logic and better input validation."

    def _spawn_candidate(self, hypothesis: str) -> EvolutionCandidate:
        """Create a new candidate record and kick off the async pipeline."""
        parent_gen = self._get_latest_generation()
        gen_id = f"v{int(parent_gen.lstrip('v')) + 1:03d}" if parent_gen else "v001"

        candidate = EvolutionCandidate(
            candidate_id=str(uuid4()),
            parent_generation=parent_gen or "v000",
            generation_id=gen_id,
            hypothesis=hypothesis,
            change_set={},  # filled in _apply_change
        )
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)

        # Run the full pipeline in the background (here synchronously for demo)
        self._run_pipeline(candidate)

        return candidate

    def _run_pipeline(self, candidate: EvolutionCandidate) -> None:
        """
        Execute the full evolution pipeline for a single candidate.
        This is synchronous for the scaffold; production would use a task queue.
        """
        try:
            # 1️⃣ Create isolated workspace
            ws = self._create_workspace(candidate.generation_id)

            # 2️⃣ Apply code change (placeholder – real impl would parse hypothesis)
            self._apply_change(ws, candidate)

            # 3️⃣ Install dependencies (if any)
            self._install_deps(ws)

            # 4️⃣ Run test suite
            test_ok = self._run_tests(ws)
            if not test_ok:
                self._mark_rejected(candidate, "Tests failed")
                return

            # 5️⃣ Run benchmarks
            bench_results = self._run_benchmarks(ws)
            candidate.benchmark_results = bench_results

            # 6️⃣ Security analysis (placeholder)
            sec_results = self._security_analysis(ws)
            candidate.security_results = sec_results

            # 7️⃣ Governance gate
            gov_decision = self.governance.is_allowed(
                operation="self_modification",
                resource=f"generation:{candidate.generation_id}",
                requester="evolution_engine",
            )
            if gov_decision != "ALLOW":
                self._mark_rejected(candidate, f"Governance {gov_decision}")
                return

            # 8️⃣ Canary deployment (placeholder)
            canary_ok = self._canary_deploy(ws, candidate)
            if not canary_ok:
                self._mark_rejected(candidate, "Canary failed")
                return

            # 9️⃣ Promote
            self._promote(candidate)

        except Exception as exc:
            self._mark_rejected(candidate, f"Pipeline exception: {exc}")

    # ------------------------------------------------------------------
    # Pipeline stage implementations (highly simplified)
    # ------------------------------------------------------------------
    def _get_latest_generation(self) -> Optional[str]:
        latest = (
            self.db.query(EvolutionCandidate)
            .order_by(EvolutionCandidate.created_at.desc())
            .first()
        )
        return latest.generation_id if latest else None

    def _create_workspace(self, generation_id: str) -> Path:
        """Copy current source tree to an isolated directory."""
        ws = self.workspace_root / generation_id
        if ws.exists():
            shutil.rmtree(ws)
        # In a real system, copy the actual backend source:
        # shutil.copytree("/path/to/vortex/backend", ws)
        ws.mkdir(parents=True)
        # Place a marker so we know the workspace exists
        (ws / "WORKSPACE_READY").write_text(generation_id)
        return ws

    def _apply_change(self, workspace: Path, candidate: EvolutionCandidate) -> None:
        """
        Apply the code change described in the hypothesis.
        For the scaffold we just write a dummy patch file.
        """
        patch_file = workspace / "candidate_patch.json"
        change_set = {
            "files_modified": ["app/core/orchestration.py"],
            "diff": "# placeholder diff – add retry logic\n",
        }
        patch_file.write_text(json.dumps(change_set, indent=2))
        candidate.change_set = change_set
        self.db.commit()

    def _install_deps(self, workspace: Path) -> None:
        """Install Python dependencies inside the workspace (if requirements.txt exists)."""
        req = workspace / "requirements.txt"
        if req.exists():
            subprocess.run(
                ["pip", "install", "-r", str(req)],
                cwd=workspace,
                capture_output=True,
                timeout=120,
            )

    def _run_tests(self, workspace: Path) -> bool:
        """Execute the test suite – return True if all pass."""
        # In reality: subprocess.run(["pytest", "-q"], cwd=workspace, ...)
        # For scaffold, always succeed
        return True

    def _run_benchmarks(self, workspace: Path) -> Dict[str, Any]:
        """Run the Vortex Benchmark suite and return structured results."""
        # Placeholder – real implementation would invoke benchmark harness
        return {
            "reasoning": 0.92,
            "planning": 0.88,
            "tool_selection": 0.95,
            "latency_ms": 120,
            "cost_usd": 0.003,
        }

    def _security_analysis(self, workspace: Path) -> Dict[str, Any]:
        """Static / dynamic security checks – placeholder."""
        return {"bandit_issues": 0, "secrets_found": 0, "risk_score": 0.1}

    def _canary_deploy(self, workspace: Path, candidate: EvolutionCandidate) -> bool:
        """
        Deploy candidate to a canary environment (separate process / container)
        and monitor for a short period.
        """
        # Placeholder – in reality spawn a separate Vortex instance with the candidate code
        return True

    def _promote(self, candidate: EvolutionCandidate) -> None:
        """Mark candidate as promoted and update the 'stable' symlink / release dir."""
        candidate.decision = "promote"
        candidate.promoted_at = datetime.utcnow()
        self.db.commit()

        # Persist release artifact
        release_dir = Path("releases") / candidate.generation_id
        release_dir.mkdir(parents=True, exist_ok=True)
        (release_dir / "candidate.json").write_text(
            json.dumps(
                {
                    "candidate_id": candidate.candidate_id,
                    "generation_id": candidate.generation_id,
                    "hypothesis": candidate.hypothesis,
                    "benchmark_results": candidate.benchmark_results,
                    "security_results": candidate.security_results,
                    "promoted_at": candidate.promoted_at.isoformat(),
                },
                indent=2,
            )
        )

    def _mark_rejected(self, candidate: EvolutionCandidate, reason: str) -> None:
        candidate.decision = "reject"
        candidate.benchmark_results = {"rejection_reason": reason}
        self.db.commit()


# ----------------------------------------------------------------------
# Factory
# ----------------------------------------------------------------------
def EvolutionEngineFactory(db: Session) -> EvolutionEngine:
    # Governance is needed; create a temporary one if not provided
    from ..governance.governance import GovernanceEngine
    gov = GovernanceEngine(db)
    return EvolutionEngine(db, gov)