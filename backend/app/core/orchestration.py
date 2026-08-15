"""Orchestration layer – stateful task execution and coordination."""

from __future__ import annotations
from typing import Dict, Any, Optional, List
from uuid import uuid4
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from ..models import Task, TaskExecution, User, Agent
from ..core.memory_system import recall, add_memory, full_context
from ..council.council import Council
from ..governance.governance import GovernanceEngine
from ..tools.tool_registry import ToolRegistry
from ..sovereign.sovereign import SovereignEngine
from ..knowledge.graph import KnowledgeGraph
from ..evolution.evolution_engine import EvolutionEngine
from ..observability.trace import start_trace, end_trace

# ----------------------------------------------------------------------
# Task state machine definition
# ----------------------------------------------------------------------
class TaskState:
    PENDING = "pending"
    PLANNING = "planning"
    DECOMPOSING = "decomposing"
    ROUTING = "routing"
    EXECUTING = "executing"
    OBSERVING = "observing"
    EVALUATING = "evaluating"
    RESOLVING = "resolving"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskProcessor:
    """
    Main entry point for executing orchestrated tasks.
    Responsibilities:
      • Load a task and its dependencies.
      • Run the state machine until completion or failure.
      • Persist task execution traces.
      • Coordinate Council, Governance, Tool execution, Memory, Knowledge Graph,
        Evolution, and Self‑Improvement.
    """

    def __init__(
        self,
        db: Session,
        user_id: str,
        sovereign: SovereignEngine,
        council: Council,
        governance: GovernanceEngine,
        tools: ToolRegistry,
        knowledge_graph: KnowledgeGraph,
        evolution_engine: EvolutionEngine,
    ) -> None:
        self.db = db
        self.user_id = user_id
        self.sovereign = sovereign
        self.council = council
        self.governance = governance
        self.tools = tools
        self.knowledge_graph = knowledge_graph
        self.evolution_engine = evolution_engine
        self.trace_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def execute_task(self, task_id: str) -> Dict[str, Any]:
        """
        Orchestrates a single task through its lifecycle.
        Returns the final result payload.
        """
        self.trace_id = start_trace(task_id=task_id)
        try:
            db = self.db
            # Load task + user linkage
            task = (
                db.query(Task)
                .filter_by(task_id=task_id, user_id=self.user_id)
                .first()
            )
            if not task:
                raise ValueError(f"Task '{task_id}' not found")
            user = (
                db.query(User).filter_by(user_id=self.user_id).first()
            )
            if not user:
                raise ValueError(f"User '{self.user_id}' not found")

            # Ensure the task has an associated agent if required
            agent_id = task.agent_id or self._select_default_agent()
            agent = (
                db.query(Agent)
                .filter_by(agent_id=agent_id, user_id=self.user_id)
                .first()
            )
            if not agent:
                raise ValueError(f"Agent '{agent_id}' not found")

            # ------------------------------------------------------------------
            # 1️⃣ Load / inject relevant memory context
            # ------------------------------------------------------------------
            memory_context = full_context(user_id=self.user_id, agent_id=agent_id)
            # Attach context to the task description for planning
            if not task.description:
                task.description = memory_context

            # ------------------------------------------------------------------
            # 2️⃣ Planning – Council proposes candidate plans
            # ------------------------------------------------------------------
            council_output = self.council.propose(task.description, agent_id=agent_id)
            # council_output is a dict with keys: "plan", "confidence", "evidence"
            plan = council_output["plan"]
            confidence = council_output.get("confidence", 0.0)
            evidence = council_output.get("evidence", [])

            # Store council proposal in memory for auditability
            add_memory(
                user_id=self.user_id,
                content=f"Council proposal (confidence={confidence}) – {plan}",
                metadata={"source": "council", "evidence": evidence},
            )

            # ------------------------------------------------------------------
            # 3️⃣ Decompose / Routing – break plan into subtasks
            # ------------------------------------------------------------------
            subtasks = self._decompose(task.description, plan)
            task.dependencies = subtasks
            db.commit()

            # ------------------------------------------------------------------
            # 4️⃣ Execute subtasks (recursively) – may involve tool calls
            # ------------------------------------------------------------------
            execution_results = []
            for sub in subtasks:
                sub_result = self._execute_subtask(sub, agent_id)
                execution_results.append(sub_result)
                # Update dependent fields (e.g., status) based on sub_result
                if sub_result["status"] == "failed":
                    # Immediate failure handling
                    task.status = TaskState.FAILED
                    db.commit()
                    self._failed_task_cleanup(task, sub_result)
                    return self._wrap_up(task, execution_results)

            # ------------------------------------------------------------------
            # 5️⃣ Observation – collect results, store them
            # ------------------------------------------------------------------
            observed = self._observe_results(task, execution_results)
            # Persist observation to memory
            add_memory(
                user_id=self.user_id,
                content=f"Observations: {observed}",
                metadata={"origin": "observation"},
            )

            # ------------------------------------------------------------------
            # 6️⃣ Evaluation – score the outcome against criteria
            # ------------------------------------------------------------------
            evaluation_score = self._evaluate_outcome(task, observed)
            # Persist evaluation for future learning
            add_memory(
                user_id=self.user_id,
                content=f"Evaluation score={evaluation_score}",
                metadata={"origin": "evaluation"},
            )

            # ------------------------------------------------------------------
            # 7️⃣ Resolution – decide next step (continue, iterate, resolve)
            # ------------------------------------------------------------------
            resolution = self._resolve_next_step(task, observed, evaluation_score)
            if resolution["next_state"] == TaskState.COMPLETED:
                task.status = TaskState.COMPLETED
                # Store final result
                add_memory(
                    user_id=self.user_id,
                    content=f"Completed successfully – result: {resolution['result']}",
                    metadata={"origin": "completion"},
                )
                task.completed_at = datetime.utcnow()
                db.commit()
                return resolution["result"]
            else:
                # Transition to next state
                task.status = resolution["next_state"]
                task.updated_at = datetime.utcnow()
                db.commit()
                # Loop back into state machine (re‑execute)
                return self.execute_task(task_id)

        except Exception as exc:
            # ------------------------------------------------------------------
            # 8️⃣ Error handling – safe fallback + logging + rollback
            # ------------------------------------------------------------------
            task.status = TaskState.FAILED
            db.commit()
            self._log_error(task.task_id, str(exc))
            # Attempt a rollback to a known‑good generation (see EvolutionEngine)
            self.evolution_engine.handle_failure(task.task_id, str(exc))
            return {"error": str(exc), "trace_id": self.trace_id}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _select_default_agent(self) -> str:
        """Pick a default agent from the user's fleet if none is specified."""
        agent = (
            self.db.query(Agent)
            .filter_by(user_id=self.user_id)
            .order_by(Agent.created_at.desc())
            .first()
        )
        if agent:
            return agent.agent_id
        # Fallback – create a lightweight “default_agent”
        default_id = str(uuid4())
        self.db.add(Agent(agent_id=default_id, name="default_agent", role="generalist", user_id=self.user_id))
        self.db.commit()
        return default_id

    def _decompose(self, task_desc: str, plan: str) -> List[str]:
        """Break the high‑level plan into concrete subtask IDs or descriptions."""
        # In a full implementation this would use an LLM or rule engine.
        # Here we simply split on commas for a deterministic demo.
        parts = [p.strip() for p in plan.split(",") if p.strip()]
        # Ensure each part has a unique ID for DB storage
        ids = []
        for i, part in enumerate(parts):
            sub_id = f"sub_{i}_{uuid4().hex[:8]}"
            ids.append(sub_id)
            # Persist a minimal Task entry for the sub‑task
            sub_task = Task(
                task_id=sub_id,
                user_id=self.user_id,
                agent_id=self._select_default_agent(),
                title=part[:64],
                description=part,
                status=TaskState.PENDING,
                max_retries=1,
                timeout_seconds=120,
            )
            self.db.merge(sub_task)
            self.db.commit()
        return ids

    def _execute_subtask(self, sub_id: str, agent_id: str) -> Dict[str, Any]:
        """
        Execute a single sub‑task.
        This is where tool calls happen after governance approval.
        """
        # Load sub‑task row
        sub_task = (
            self.db.query(Task)
            .filter_by(task_id=sub_id, user_id=self.user_id)
            .first()
        )
        if not sub_task:
            raise ValueError(f"Sub‑task '{sub_id}' not found")
        sub_task.status = TaskState.EXECUTING
        self.db.commit()

        # ------------------------------------------------------------------
        # 8️⃣ Governance gate before any tool execution
        # ------------------------------------------------------------------
        allowed = self.governance.is_allowed(
            operation=f"subtask_{sub_id}",
            resource="/tmp",  # placeholder – real resources are derived from context
            requester=agent_id,
        )
        if not allowed:
            # Record deny
            self.governance.log_decision(
                operation=f"subtask_{sub_id}",
                decision="DENY",
                rationale="Governance block – insufficient permissions",
                requested_by=agent_id,
            )
            raise PermissionError(f"Governance denied execution of subtask {sub_id}")

        # ------------------------------------------------------------------
        # 9️⃣ Tool execution (example: a simple 'shell' command)
        # ------------------------------------------------------------------
        # For demo purposes we just touch a file to signal completion.
        # Real implementation would dispatch to ToolRegistry based on plan.
        try:
            # Simulate a lightweight operation (e.g., create a marker file)
            marker_path = f"/tmp/vortex_{sub_id}.marker"
            Path(marker_path).write_text(f"Handled {sub_id}")
            sub_task.status = TaskState.SUCCEEDED
            self.db.commit()
            # Persist execution record
            exec_rec = TaskExecution(
                task_id=sub_id,
                executor_agent_id=agent_id,
                started_at=datetime.utcnow(),
                status="succeeded",
                output=f"Wrote marker {marker_path}",
                tool_name="local_file_write",
                tool_input={"path": marker_path, "content": f"Handled {sub_id}"},
            )
            self.db.add(exec_rec)
            self.db.commit()
            return {
                "sub_id": sub_id,
                "status": "succeeded",
                "output": f"Marker written to {marker_path}",
                "execution_id": exec_rec.execution_id,
            }
        except Exception as sub_exc:
            sub_task.status = TaskState.FAILED
            self.db.commit()
            # Record failure for governance audit
            self.governance.log_decision(
                operation=f"subtask_{sub_id}",
                decision="FAIL",
                rationale=str(sub_exc),
                requested_by=agent_id,
            )
            raise sub_exc

    def _observe_results(self, task: Task, exec_results: List[Dict[str, Any]]) -> str:
        """Compose observations from subtask executions."""
        # Simple concatenation of all outputs
        observations = [r["output"] for r in exec_results if "output" in r]
        return "\n".join(observations) if observations else "No observable output"

    def _evaluate_outcome(self, task: Task, observations: str) -> float:
        """Score the outcome – placeholder for more elaborate metrics."""
        # Very naive placeholder: 1.0 if observations contain “succeeded”, else 0.5
        return 1.0 if "succeeded" in observations else 0.5

    def _resolve_next_step(
        self, task: Task, observations: str, score: float
    ) -> Dict[str, Any]:
        """
        Decide whether to proceed, iterate, request more evidence, or finish.
        Returns dict with keys: next_state, result (if completed), decision_reason.
        """
        # Simple heuristic: if score >= 0.9 we are done, else loop again.
        if score >= 0.9:
            return {
                "next_state": TaskState.COMPLETED,
                "result": f"Task {task.task_id} completed with high confidence.",
            }
        else:
            # Request Council to revisit with more evidence
            return {
                "next_state": TaskState.PLANNING,
                "result": "Re‑plan with additional evidence.",
            }

    def _failed_task_cleanup(self, task: Task, sub_result: Dict[str, Any]) -> None:
        """Undo partial work that led to a failure (e.g., delete temp files)."""
        # Simple cleanup – delete marker files created earlier
        for r in sub_result.get("files_created", []):
            try:
                Path(r).unlink(missing_ok=True)
            except Exception:
                pass

    def _log_error(self, task_id: str, error_msg: str) -> None:
        """Centralised error logging."""
        # Could integrate with Observability/tracing system
        print(f"[ERROR] Task {task_id} failed: {error_msg}")

    def _wrap_up(self, task: Task, execution_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Package final result for external consumers."""
        return {
            "task_id": task.task_id,
            "final_status": task.status,
            "trace_id": self.trace_id,
            "executions": execution_results,
        }

    def _lookup_error(entity_id: str, entity_type: str) -> Exception:
        """Helper to raise a consistent lookup error."""
        return ValueError(f"{entity_type} '{entity_id}' not found")


# ----------------------------------------------------------------------
# Factory to wire dependencies together (used by API routers)
# ----------------------------------------------------------------------
def create_task_processor(
    db: Session, user_id: str
) -> TaskProcessor:
    """
    Constructs a fully‑wired TaskProcessor with all required collaborators.
    This factory lives in the backend entry point and is used by the
    `/api/v1/tasks/{task_id}` endpoint.
    """
    from ..memory.memory_system import MemoryBackend
    from ..council.council import CouncilFactory
    from ..governance.governance import GovernanceFactory
    from ..tools.tool_registry import ToolRegistryFactory
    from ..sovereign.sovereign import SovereignFactory
    from ..knowledge.graph import KnowledgeGraphFactory
    from ..evolution.evolution_engine import EvolutionEngineFactory

    # ---- Memory -------------------------------------------------------
    memory_backend = MemoryBackend(db)  # thin wrapper around MemoryEntry CRUD
    # The MemoryBackend can be injected where needed; for brevity we keep it internal.

    # ---- Knowledge Graph -----------------------------------------------
    kg = KnowledgeGraphFactory(db)

    # ---- Evolution Engine -----------------------------------------------
    evolution = EvolutionEngineFactory(db)

    # ---- Sovereign -------------------------------------------------------
    sovereign = SovereignFactory(db)

    # ---- Council --------------------------------------------------------
    council = CouncilFactory(db, sovereign, kg)

    # ---- Governance ----------------------------------------------------
    governance = GovernanceFactory(db)

    # ---- Tool Registry --------------------------------------------------
    tools = ToolRegistryFactory(db, governance)

    # ---- Assemble processor --------------------------------------------
    processor = TaskProcessor(
        db=db,
        user_id=user_id,
        sovereign=sovereign,
        council=council,
        governance=governance,
        tools=tools,
        knowledge_graph=kg,
        evolution_engine=evolution,
    )
    return processor