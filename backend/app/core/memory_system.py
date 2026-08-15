"""Core memory system – thin wrapper around the MemoryEntry model."""

from typing import List, Optional, Dict, Any
from uuid import uuid4

from sqlalchemy.orm import Session
from ..models import MemoryEntry, User, Agent, SessionLocal
from ..vortex.config import SQLITE_URL

# ----------------------------------------------------------------------
# Session handling – one session per operation (fastapi will manage longer-lived sessions)
# ----------------------------------------------------------------------
def _get_db() -> Session:
    """Yield a fresh SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----------------------------------------------------------------------
# Helper – ensure user / agent existence
# ----------------------------------------------------------------------
def _ensure_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        user = User(user_id=user_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _ensure_agent(db: Session, agent_id: str, user_id: str, name: str, role: str) -> Agent:
    agent = db.query(Agent).filter_by(agent_id=agent_id).first()
    if not agent:
        agent = Agent(
            agent_id=agent_id,
            name=name,
            role=role,
            user_id=user_id,
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
    return agent


# ----------------------------------------------------------------------
# MemoryEntry CRUD
# ----------------------------------------------------------------------
def add_memory(
    *,
    user_id: str,
    content: str,
    agent_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    confidence: Optional[float] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> MemoryEntry:
    """
    Persist a new memory fact.

    Returns the created MemoryEntry instance.
    """
    if not content:
        raise ValueError("Memory content cannot be empty")

    # Resolve agent if supplied
    db_agent = None
    if agent_id:
        # Ensure user exists first
        db_user = _ensure_user(_get_db(), user_id)
        db_agent = _ensure_agent(_get_db(), agent_id, user_id, name="unnamed", role="memory_agent")
        # Attach agent_id for later linking
        agent_id_obj = agent_id
    else:
        agent_id_obj = None

    # Create entry
    entry = MemoryEntry(
        memory_id=str(uuid4()),
        user_id=user_id,
        agent_id=agent_id_obj,
        content=content,
        metadata=metadata or {},
        confidence=confidence,
        provenance=provenance or {},
    )
    # Insert
    db = next(_get_db())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def recall(
    *,
    user_id: str,
    query: str,
    limit: int = 10,
    filter_by_agent: Optional[str] = None,
    min_score: Optional[float] = None,
) -> List[MemoryEntry]:
    """
    Semantic recall – in a real deployment this would use a vector store.
    For now we perform a simple case‑insensitive substring search.
    """
    db = next(_get_db())
    # Basic filtering
    q = db.query(MemoryEntry).filter_by(user_id=user_id)
    if filter_by_agent:
        q = q.filter_by(agent_id=filter_by_agent)

    # Very naive “semantic” filter – placeholder for real embedding search
    results = q.all()
    # Simple relevance scoring based on keyword overlap
    lowered_query = query.lower()
    scored = []
    for mem in results:
        lowered = mem.content.lower()
        score = lowered.count(lowered_query)
        if min_score is not None and score < min_score:
            continue
        scored.append((score, mem))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [mem for _, mem in scored[:limit]]


def update_memory(
    *,
    memory_id: str,
    new_content: str,
    user_id: str,
    agent_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> MemoryEntry:
    """
    Update an existing memory entry.  Raises if not found or does not belong
    to the caller.
    """
    db = next(_get_db())
    entry = (
        db.query(MemoryEntry)
        .filter_by(memory_id=memory_id, user_id=user_id)
        .first()
    )
    if not entry:
        raise lookup_error(memory_id, "memory entry")

    # Optional: re‑validate agent scope
    if agent_id and entry.agent_id != agent_id:
        raise PermissionError("Agent mismatch for memory update")

    entry.content = new_content
    entry.metadata = metadata or {}
    db.commit()
    db.refresh(entry)
    return entry


def delete_memory(
    *,
    memory_id: str,
    user_id: str,
    require_agent: Optional[str] = None,
) -> bool:
    """
    Delete a memory entry. Returns True if a row was removed.
    """
    db = next(_get_db())
    query = db.query(MemoryEntry).filter_by(memory_id=memory_id, user_id=user_id)
    if require_agent:
        query = query.filter_by(agent_id=require_agent)
    deleted_count = query.delete()
    db.commit()
    return deleted_count > 0


def list_all_memories(
    *,
    user_id: str,
    agent_id: Optional[str] = None,
    include_expired: bool = False,
) -> List[MemoryEntry]:
    """
    List every stored memory for a user (optionally filtered by agent).
    """
    db = next(_get_db())
    query = db.query(MemoryEntry).filter_by(user_id=user_id)
    if agent_id:
        query = query.filter_by(agent_id=agent_id)
    if not include_expired:
        # Assume `expires_at` is a DateTime; keep only non‑expired rows
        from datetime import datetime
        query = query.filter(MemoryEntry.expires_at.is_(None) | (MemoryEntry.expires_at > datetime.utcnow()))
    return db.query(MemoryEntry).order_by(MemoryEntry.created_at.desc()).all()


def full_context(
    *,
    user_id: str,
    agent_id: Optional[str] = None,
) -> str:
    """
    Retrieve a concatenated string of all memories for a user/agent.
    Used as LLM context injection.
    """
    memories = list_all_memories(user_id=user_id, agent_id=agent_id)
    return "\n\n---\n\n".join(m.content for m in memories)


# ----------------------------------------------------------------------
# Simple error helper
# ----------------------------------------------------------------------
def lookup_error(entity_id: str, entity_type: str) -> Exception:
    return ValueError(f"{entity_type} '{entity_id}' not found")