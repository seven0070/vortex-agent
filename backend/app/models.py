"""Vortex Agent backend core models."""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Text,
    Float,
    JSON,
    LargeBinary,
    Index,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

# ----------------------------------------------------------------------
# Database configuration
# ----------------------------------------------------------------------
from .vortex.config import SQLITE_URL

Base = declarative_base()
_engine = create_engine(SQLITE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def create_engine_from_config():
    """Return the shared SQLAlchemy engine (used for create_all on startup)."""
    return _engine


# ----------------------------------------------------------------------
# Core model definitions
# ----------------------------------------------------------------------
class User(Base):
    """User / owner of memories and agent sessions."""
    __tablename__ = "users"

    user_id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email: str = Column(String, nullable=True)
    created_at: DateTime = Column(DateTime, default=datetime.utcnow)
    preferences: JSON = Column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<User user_id={self.user_id} email={self.email}>"


class Agent(Base):
    """Autonomous agent instance."""
    __tablename__ = "agents"

    agent_id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: str = Column(String, nullable=False)
    role: str = Column(String, nullable=False)
    user_id: str = Column(String, nullable=False)
    created_at: DateTime = Column(DateTime, default=datetime.utcnow)
    model_config: JSON = Column(JSON, nullable=True)

    user = Column(String, nullable=False)  # Denormalized for quick lookup
    __table_args__ = (Index("ix_agents_user_id_role", "user_id", "role"),)

    def __repr__(self) -> str:
        return f"<Agent agent_id={self.agent_id} name={self.name} role={self.role}>"


class MemoryEntry(Base):
    """Persisted memory / fact."""
    __tablename__ = "memories"

    memory_id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: str = Column(String, nullable=False)
    agent_id: str = Column(String, nullable=True)
    content: Text = Column(Text, nullable=False)
    embedding: LargeBinary = Column(LargeBinary, nullable=True)
    meta_data: JSON = Column(JSON, nullable=True)
    created_at: DateTime = Column(DateTime, default=datetime.utcnow)
    expires_at: DateTime = Column(DateTime, nullable=True)
    confidence: Float = Column(Float, nullable=True)
    provenance: JSON = Column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_memories_user_id", "user_id"),
        Index("ix_memories_agent_id", "agent_id"),
        Index("ix_memories_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<MemoryEntry memory_id={self.memory_id} user_id={self.user_id}>"


class KnowledgeNode(Base):
    """Node in the knowledge graph."""
    __tablename__ = "knowledge_nodes"

    node_id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: str = Column(String, nullable=False)
    agent_id: str = Column(String, nullable=True)
    entity_type: str = Column(String, nullable=False)  # person, project, concept, etc.
    name: str = Column(String, nullable=False)
    properties: JSON = Column(JSON, nullable=True)
    created_at: DateTime = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<KnowledgeNode node_id={self.node_id} entity={self.entity_type} name={self.name}>"


class KnowledgeEdge(Base):
    """Edge connecting two knowledge nodes."""
    __tablename__ = "knowledge_edges"

    edge_id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_node: str = Column(String, nullable=False)  # node_id of source
    target_node: str = Column(String, nullable=False)  # node_id of target
    relationship: str = Column(String, nullable=False)  # e.g. "depends_on", "improves"
    weight: Float = Column(Float, default=1.0)
    created_at: DateTime = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_knowledge_edges_source_node", "source_node"),
        Index("ix_knowledge_edges_target_node", "target_node"),
        Index("ix_knowledge_edges_relationship", "relationship"),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeEdge edge_id={self.edge_id} src={self.source_node} tgt={self.target_node} rel={self.relationship}>"


class Task(Base):
    """Orchestrated unit of work."""
    __tablename__ = "tasks"

    task_id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: str = Column(String, nullable=False)
    agent_id: str = Column(String, nullable=True)
    title: str = Column(String, nullable=False)
    description: Text = Column(Text, nullable=True)
    status: str = Column(String, nullable=False, default="pending")  # pending, running, succeeded, failed, cancelled
    created_at: DateTime = Column(DateTime, default=datetime.utcnow)
    updated_at: DateTime = Column(DateTime, onupdate=datetime.utcnow)
    dependencies: JSON = Column(JSON, default=list)
    max_retries: int = Column(Integer, default=1)
    timeout_seconds: int = Column(Integer, default=300)
    checkpoint_path: str = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Task task_id={self.task_id} status={self.status}>"


class TaskExecution(Base):
    """Result of executing a task (or subtask)."""
    __tablename__ = "task_executions"

    execution_id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: str = Column(String, nullable=False)
    executor_agent_id: str = Column(String, nullable=True)
    started_at: DateTime = Column(DateTime, default=datetime.utcnow)
    finished_at: DateTime = Column(DateTime, nullable=True)
    status: str = Column(String, nullable=False, default="started")  # started, succeeded, failed, timed_out
    output: Text = Column(Text)
    error: Text = Column(Text)
    tool_name: str = Column(String, nullable=True)
    tool_input: JSON = Column(JSON, nullable=True)
    retry_of: str = Column(String, nullable=True)  # execution_id of parent execution if retried

    __table_args__ = (
        Index("ix_task_executions_task_id", "task_id"),
        Index("ix_task_executions_executor_agent_id", "executor_agent_id"),
        Index("ix_task_executions_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<TaskExecution execution_id={self.execution_id} status={self.status}>"


class GovernanceLog(Base):
    """Record of governance decisions."""
    __tablename__ = "governance_logs"

    log_id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    operation: str = Column(String, nullable=False)  # e.g., "file_write", "shell_exec"
    resource: str = Column(String, nullable=False)
    decision: str = Column(String, nullable=False)  # "ALLOW", "DENY", "ESCALATE"
    rationale: Text = Column(Text)
    requested_by: str = Column(String, nullable=False)  # agent_id
    timestamp: DateTime = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<GovernanceLog log_id={self.log_id} operation={self.operation} decision={self.decision}>"


class SovereignState(Base):
    """Strategic control state."""
    __tablename__ = "sovereign_state"

    id: int = Column(Integer, primary_key=True)  # singleton row
    identity: str = Column(Text, nullable=False)
    long_term_objectives: JSON = Column(JSON, nullable=False)
    current_objectives: JSON = Column(JSON, nullable=False)
    priorities: JSON = Column(JSON, nullable=False)
    system_state: JSON = Column(JSON, nullable=False)
    lifecycle_phase: str = Column(String, nullable=False, default="born")  # born, operational, canary, deployed, monitored, rollback
    created_at: DateTime = Column(DateTime, default=datetime.utcnow)
    updated_at: DateTime = Column(DateTime, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<SovereignState id={self.id}>"


class EvolutionCandidate(Base):
    """Candidate change set for self‑improvement."""
    __tablename__ = "evolution_candidates"

    candidate_id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_generation: str = Column(String, nullable=False)
    generation_id: str = Column(String, nullable=False)
    hypothesis: Text = Column(Text)
    change_set: JSON = Column(JSON, nullable=False)
    benchmark_results: JSON = Column(JSON, nullable=True)
    security_results: JSON = Column(JSON, nullable=True)
    performance_results: JSON = Column(JSON, nullable=True)
    decision: str = Column(String, nullable=False, default="pending")  # pending, promote, reject, rollback
    created_at: DateTime = Column(DateTime, default=datetime.utcnow)
    promoted_at: DateTime = Column(DateTime, nullable=True)
    rolled_back_at: DateTime = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<EvolutionCandidate candidate_id={self.candidate_id}>"


class BenchmarkRun(Base):
    """Result of a benchmark execution."""
    __tablename__ = "benchmark_runs"

    run_id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id: str = Column(String, nullable=False)
    benchmark_name: str = Column(String, nullable=False)
    score: Float = Column(Float, nullable=False)
    meta_data: JSON = Column(JSON, nullable=True)
    executed_at: DateTime = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<BenchmarkRun run_id={self.run_id}>"


# ----------------------------------------------------------------------
# Hermes-like chat core models (sessions + messages)
# ----------------------------------------------------------------------
class ChatSession(Base):
    """A chat session in the Hermes-like streaming chat core."""

    __tablename__ = "chat_sessions"

    id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: str = Column(String, default="New chat")
    created_at: DateTime = Column(DateTime, default=datetime.utcnow)
    updated_at: DateTime = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<ChatSession id={self.id} title={self.title}>"


class ChatMessage(Base):
    """A single message inside a chat session."""

    __tablename__ = "chat_messages"

    id: str = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: str = Column(String, nullable=False, index=True)
    role: str = Column(String, nullable=False)  # user | assistant | tool
    content: Text = Column(Text, nullable=False)
    created_at: DateTime = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ChatMessage id={self.id} role={self.role}>"