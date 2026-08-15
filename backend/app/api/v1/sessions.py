"""
Hermes-like chat sessions router — create, list, history, delete.

All routes declare their own /sessions prefix; routers.py includes this
sub-router WITHOUT adding the prefix again (single /api/v1 from the parent).
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...models import ChatMessage, ChatSession, SessionLocal
from ...core import chat_engine

sessions_router = APIRouter(prefix="/sessions", tags=["Chat Sessions"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _session_dict(s: ChatSession, db: Session) -> dict:
    msg_count = db.query(ChatMessage).filter(ChatMessage.session_id == s.id).count()
    return {
        "id": s.id,
        "title": s.title,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        "message_count": msg_count,
    }


def _message_dict(m: ChatMessage) -> dict:
    return {
        "id": m.id,
        "session_id": m.session_id,
        "role": m.role,
        "content": m.content,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@sessions_router.post("")
def create_session(db: Session = Depends(get_db)):
    """Create a new chat session."""
    s = ChatSession()
    db.add(s)
    db.commit()
    db.refresh(s)
    return _session_dict(s, db)


@sessions_router.get("")
def list_sessions(limit: int = 50, db: Session = Depends(get_db)):
    """List sessions, most recently updated first."""
    sessions = (
        db.query(ChatSession)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
        .all()
    )
    return {"sessions": [_session_dict(s, db) for s in sessions]}


@sessions_router.get("/{session_id}/messages")
def get_messages(session_id: str, db: Session = Depends(get_db)):
    """Return message history for a session, oldest first."""
    s = db.get(ChatSession, session_id)
    if not s:
        raise HTTPException(404, "session not found")
    msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return {"session": _session_dict(s, db), "messages": [_message_dict(m) for m in msgs]}


@sessions_router.delete("/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Delete a session and its messages."""
    s = db.get(ChatSession, session_id)
    if not s:
        raise HTTPException(404, "session not found")
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.delete(s)
    db.commit()
    return {"ok": True, "deleted": session_id}


@sessions_router.patch("/{session_id}")
def rename_session(session_id: str, request: Dict[str, Any], db: Session = Depends(get_db)):
    """Rename a session (e.g. auto-title after first message)."""
    s = db.get(ChatSession, session_id)
    if not s:
        raise HTTPException(404, "session not found")
    title = request.get("title")
    if not title:
        raise HTTPException(400, "title required")
    s.title = title
    db.commit()
    return _session_dict(s, db)


@sessions_router.post("/{session_id}/chat")
def chat(session_id: str, request: Dict[str, Any], db: Session = Depends(get_db)):
    """Stream a chat turn for a session. Returns SSE events.

    Body: {"message": "..."}
    Events: {"type":"delta","content":...} | {"type":"tool",...}
            | {"type":"done","assistant":...} | {"type":"error","message":...}
    """
    s = db.get(ChatSession, session_id)
    if not s:
        raise HTTPException(404, "session not found")
    message = (request.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "message required")

    def event_stream():
        for evt in chat_engine.stream_chat(session_id, message):
            yield f"data: {evt}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
