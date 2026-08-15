"""API v1 routers – HTTP endpoints for all Vortex capabilities."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from uuid import uuid4
from datetime import datetime

from ...models import Task, User, Agent, MemoryEntry, KnowledgeNode, KnowledgeEdge, SessionLocal
from ...core.memory_system import add_memory, recall, full_context, update_memory, delete_memory
from ...core.orchestration import create_task_processor
from ...council.council import Council
from ...governance.governance import GovernanceEngine
from ...sovereign.sovereign import SovereignEngine
from ...knowledge.graph import KnowledgeGraphFactory
from ...evolution.evolution_engine import EvolutionEngineFactory
from ...tools.tool_registry import ToolRegistryFactory
from .settings import settings_router

# ----------------------------------------------------------------------
# Dependency – get DB session
# ----------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------------------------------------------------------------
# Router
# ----------------------------------------------------------------------
api_router = APIRouter(prefix="/api/v1", tags=["Vortex API"])

# Hermes-like settings + improve sub-router (declares its own /settings prefix)
api_router.include_router(settings_router)


# ----------------------------------------------------------------------
# Health / Version
# ----------------------------------------------------------------------
@api_router.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}


# ----------------------------------------------------------------------
# Chat / Task execution
# ----------------------------------------------------------------------
@api_router.post("/chat")
def chat(request: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Accepts:
    {
        "user_id": "uuid",
        "message": "string",
        "agent_id": "uuid (optional)"
    }
    Returns:
    {
        "response": "string",
        "task_id": "uuid (if a task was created)"
    }
    """
    user_id = request.get("user_id")
    message = request.get("message")
    agent_id = request.get("agent_id")

    if not user_id or not message:
        raise HTTPException(400, "user_id and message are required")

    # Ensure user exists
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        user = User(user_id=user_id)
        db.add(user)
        db.commit()

    # Store user message in memory
    add_memory(user_id=user_id, content=f"User: {message}", metadata={"role": "user"})

    # For now, create a task and run orchestration
    task = Task(
        task_id=str(uuid4()),
        user_id=user_id,
        agent_id=agent_id,
        title=message[:64],
        description=message,
        status="pending",
    )
    db.add(task)
    db.commit()

    # Run orchestration
    processor = create_task_processor(db, user_id)
    result = processor.execute_task(task.task_id)

    # Store assistant response
    add_memory(user_id=user_id, content=f"Assistant: {result}", metadata={"role": "assistant"})

    return {"response": result, "task_id": task.task_id}


@api_router.post("/orchestrate")
def orchestrate(request: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Explicit task orchestration endpoint.
    """
    user_id = request.get("user_id")
    description = request.get("description")
    agent_id = request.get("agent_id")

    if not user_id or not description:
        raise HTTPException(400, "user_id and description required")

    task = Task(
        task_id=str(uuid4()),
        user_id=user_id,
        agent_id=agent_id,
        title=description[:64],
        description=description,
        status="pending",
    )
    db.add(task)
    db.commit()

    processor = create_task_processor(db, user_id)
    result = processor.execute_task(task.task_id)

    return {"task_id": task.task_id, "result": result}


@api_router.get("/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter_by(task_id=task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    return {
        "task_id": task.task_id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


# ----------------------------------------------------------------------
# Council
# ----------------------------------------------------------------------
@api_router.post("/council/deliberate")
def council_deliberate(request: Dict[str, Any], db: Session = Depends(get_db)):
    user_id = request.get("user_id", "admin")
    task_description = request.get("task_description")
    if not task_description:
        raise HTTPException(400, "task_description required")

    sovereign = SovereignEngine(db)
    kg = KnowledgeGraphFactory(db)
    council = Council(sovereign, kg)
    result = council.propose(task_description, agent_id=request.get("agent_id", "default"))
    return result


# ----------------------------------------------------------------------
# Memory
# ----------------------------------------------------------------------
@api_router.post("/memory/add")
def memory_add(request: Dict[str, Any], db: Session = Depends(get_db)):
    user_id = request.get("user_id")
    content = request.get("content")
    agent_id = request.get("agent_id")
    metadata = request.get("metadata")
    if not user_id or not content:
        raise HTTPException(400, "user_id and content required")
    entry = add_memory(user_id=user_id, content=content, agent_id=agent_id, metadata=metadata)
    return {"memory_id": entry.memory_id, "created_at": entry.created_at}


@api_router.post("/memory/recall")
def memory_recall(request: Dict[str, Any], db: Session = Depends(get_db)):
    user_id = request.get("user_id")
    query = request.get("query")
    limit = request.get("limit", 10)
    agent_id = request.get("agent_id")
    if not user_id or not query:
        raise HTTPException(400, "user_id and query required")
    results = recall(user_id=user_id, query=query, limit=limit, filter_by_agent=agent_id)
    return {"memories": [{"memory_id": m.memory_id, "content": m.content, "created_at": m.created_at} for m in results]}


@api_router.get("/memory/context")
def memory_context(user_id: str, agent_id: Optional[str] = None, db: Session = Depends(get_db)):
    ctx = full_context(user_id=user_id, agent_id=agent_id)
    return {"context": ctx}


# ----------------------------------------------------------------------
# Knowledge Graph
# ----------------------------------------------------------------------
@api_router.post("/graph/nodes")
def graph_add_node(request: Dict[str, Any], db: Session = Depends(get_db)):
    kg = KnowledgeGraphFactory(db)
    node = kg.add_node(
        user_id=request.get("user_id", "admin"),
        entity_type=request.get("entity_type"),
        name=request.get("name"),
        properties=request.get("properties"),
        agent_id=request.get("agent_id"),
    )
    return {"node_id": node.node_id}


@api_router.get("/graph/nodes")
def graph_find_nodes(
    user_id: str = "admin",
    entity_type: Optional[str] = None,
    name_contains: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    kg = KnowledgeGraphFactory(db)
    nodes = kg.find_nodes(user_id=user_id, entity_type=entity_type, name_contains=name_contains, limit=limit)
    return {"nodes": [{"node_id": n.node_id, "entity_type": n.entity_type, "name": n.name, "properties": n.properties} for n in nodes]}


@api_router.post("/graph/edges")
def graph_add_edge(request: Dict[str, Any], db: Session = Depends(get_db)):
    kg = KnowledgeGraphFactory(db)
    edge = kg.add_edge(
        source_node=request.get("source_node"),
        target_node=request.get("target_node"),
        relationship=request.get("relationship"),
        weight=request.get("weight", 1.0),
    )
    return {"edge_id": edge.edge_id}


@api_router.get("/graph/neighbors")
def graph_neighbors(node_id: str, direction: str = "both", relationship: Optional[str] = None, max_depth: int = 1, db: Session = Depends(get_db)):
    kg = KnowledgeGraphFactory(db)
    results = kg.neighbors(node_id, direction=direction, relationship=relationship, max_depth=max_depth)
    return {"neighbors": [{"node": {"node_id": r["node"].node_id, "name": r["node"].name}, "edge": {"relationship": r["edge"].relationship}, "depth": r["depth"]} for r in results]}


# ----------------------------------------------------------------------
# Governance
# ----------------------------------------------------------------------
@api_router.post("/governance/check")
def governance_check(request: Dict[str, Any], db: Session = Depends(get_db)):
    gov = GovernanceEngine(db)
    decision = gov.is_allowed(
        operation=request.get("operation"),
        resource=request.get("resource"),
        requester=request.get("requester"),
    )
    return {"decision": decision}


@api_router.get("/governance/logs")
def governance_logs(limit: int = 100, db: Session = Depends(get_db)):
    from ...models import GovernanceLog
    logs = db.query(GovernanceLog).order_by(GovernanceLog.timestamp.desc()).limit(limit).all()
    return {"logs": [{"log_id": l.log_id, "operation": l.operation, "decision": l.decision, "rationale": l.rationale, "requested_by": l.requested_by, "timestamp": l.timestamp} for l in logs]}


# ----------------------------------------------------------------------
# Sovereign
# ----------------------------------------------------------------------
@api_router.get("/sovereign/status")
def sovereign_status(db: Session = Depends(get_db)):
    sovereign = SovereignEngine(db)
    return {
        "identity": sovereign.get_identity(),
        "long_term_objectives": sovereign.get_long_term_objectives(),
        "current_objectives": sovereign.get_current_objectives(),
        "priorities": sovereign.get_priorities(),
        "system_state": sovereign.get_system_state(),
        "lifecycle_phase": sovereign.get_lifecycle_phase(),
    }


@api_router.post("/sovereign/objectives")
def sovereign_set_objectives(request: Dict[str, Any], db: Session = Depends(get_db)):
    sovereign = SovereignEngine(db)
    objectives = request.get("objectives")
    if not objectives:
        raise HTTPException(400, "objectives required")
    sovereign.set_current_objectives(objectives)
    return {"status": "updated"}


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------
@api_router.get("/tools")
def list_tools(db: Session = Depends(get_db)):
    gov = GovernanceEngine(db)
    registry = ToolRegistryFactory(db, gov)
    return {"tools": [{"name": t.name, "description": t.description, "risk_level": t.risk_level.value} for t in registry.list_tools()]}


@api_router.post("/tools/execute")
def execute_tool(request: Dict[str, Any], db: Session = Depends(get_db)):
    gov = GovernanceEngine(db)
    registry = ToolRegistryFactory(db, gov)
    tool_name = request.get("tool_name")
    agent_id = request.get("agent_id")
    input_data = request.get("input_data", {})
    if not tool_name or not agent_id:
        raise HTTPException(400, "tool_name and agent_id required")
    try:
        result = registry.execute(tool_name, agent_id, input_data)
        return {"result": result}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


# ----------------------------------------------------------------------
# Evolution
# ----------------------------------------------------------------------
@api_router.post("/evolution/propose")
def evolution_propose(request: Dict[str, Any], db: Session = Depends(get_db)):
    hypothesis = request.get("hypothesis")
    if not hypothesis:
        raise HTTPException(400, "hypothesis required")
    gov = GovernanceEngine(db)
    engine = EvolutionEngineFactory(db)
    candidate = engine.propose_improvement(hypothesis)
    return {"candidate_id": candidate.candidate_id, "generation_id": candidate.generation_id, "decision": candidate.decision}


@api_router.get("/evolution/candidates")
def evolution_candidates(db: Session = Depends(get_db)):
    from ...models import EvolutionCandidate
    candidates = db.query(EvolutionCandidate).order_by(EvolutionCandidate.created_at.desc()).limit(20).all()
    return {"candidates": [{"candidate_id": c.candidate_id, "generation_id": c.generation_id, "hypothesis": c.hypothesis, "decision": c.decision, "created_at": c.created_at} for c in candidates]}


# ----------------------------------------------------------------------
# Benchmarks
# ----------------------------------------------------------------------
@api_router.get("/benchmarks")
def benchmark_runs(db: Session = Depends(get_db)):
    from ...models import BenchmarkRun
    runs = db.query(BenchmarkRun).order_by(BenchmarkRun.executed_at.desc()).limit(50).all()
    return {"runs": [{"run_id": r.run_id, "candidate_id": r.candidate_id, "benchmark_name": r.benchmark_name, "score": r.score, "executed_at": r.executed_at} for r in runs]}


# ----------------------------------------------------------------------
# Observability
# ----------------------------------------------------------------------
@api_router.get("/observability/trace")
def get_trace(trace_id: str):
    # In a real implementation, query a trace store
    return {"trace_id": trace_id, "message": "Trace querying not yet implemented"}


# ----------------------------------------------------------------------
# Agent management
# ----------------------------------------------------------------------
@api_router.post("/agents")
def create_agent(request: Dict[str, Any], db: Session = Depends(get_db)):
    user_id = request.get("user_id")
    name = request.get("name")
    role = request.get("role")
    if not user_id or not name or not role:
        raise HTTPException(400, "user_id, name, role required")
    agent = Agent(
        agent_id=str(uuid4()),
        name=name,
        role=role,
        user_id=user_id,
    )
    db.add(agent)
    db.commit()
    return {"agent_id": agent.agent_id, "name": agent.name, "role": agent.role}


@api_router.get("/agents")
def list_agents(user_id: str, db: Session = Depends(get_db)):
    agents = db.query(Agent).filter_by(user_id=user_id).all()
    return {"agents": [{"agent_id": a.agent_id, "name": a.name, "role": a.role} for a in agents]}