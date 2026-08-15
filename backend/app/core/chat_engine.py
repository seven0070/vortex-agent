"""
ChatEngine — Hermes-like streaming chat loop with tool calling.

Flow per user message:
  1. Load session history
  2. Append user message (persisted)
  3. Call LLM (non-streaming) with tool schemas
  4. If tool calls requested (structured OR embedded in content JSON):
       execute tools, feed results back, loop (max 8)
  5. Stream the final answer as SSE deltas; persist assistant message

The "extras" (Council/Governance/Sovereign/etc.) are deliberately NOT in this
path — they remain background services via /orchestrate.

Note: the local hermes proxy may emit tool calls as plain text content
(`{"tool_calls": [...]}`) instead of the structured `tool_calls` field, so we
handle both.
"""

import json
import re
from typing import Generator, List

from ..models import ChatMessage, ChatSession, SessionLocal
from . import llm_client
from . import tools as tool_registry

MAX_TOOL_ITERATIONS = 8
SYSTEM_PROMPT = (
    "You are Vortex, an autonomous local-first AI agent running inside the "
    "Vortex Agent desktop app. You have access to tools for inspecting and "
    "modifying the vortex-agent repository (terminal, read_file, write_file, "
    "list_files, now). Be concise, correct, and verify your work. If you use "
    "tools, briefly summarize what you did."
)


def _db():
    return SessionLocal()


def _history_messages(db, session_id: str) -> List[dict]:
    msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in msgs if m.role in ("user", "assistant")]


def _persist(db, session_id: str, role: str, content: str) -> None:
    m = ChatMessage(session_id=session_id, role=role, content=content)
    db.add(m)
    db.commit()


def _touch_session(db, session_id: str) -> None:
    db.commit()  # updated_at onupdate fires


def _parse_tool_calls(message: dict) -> List[dict]:
    """Extract tool calls from an assistant message (both formats)."""
    # Format 1: structured field
    tcs = message.get("tool_calls")
    if tcs:
        return [
            {
                "id": tc.get("id", ""),
                "type": "function",
                "function": tc.get("function", {}),
            }
            for tc in tcs
        ]

    # Format 2: embedded in content as JSON text (hermes proxy behavior)
    content = message.get("content") or ""
    m = re.search(r"\{\"tool_calls\":.*?\}\s*$", content, re.DOTALL)
    if not m:
        m = re.search(r"\{[^{}]*\"tool_calls\"[^{}]*\}", content, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            tcs = data.get("tool_calls") or []
            if tcs:
                return [
                    {
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": tc.get("function", {}),
                    }
                    for tc in tcs
                ]
        except json.JSONDecodeError:
            pass
    return []


def _run_tool_calls(tool_calls: List[dict]) -> List[dict]:
    """Execute tool calls; return tool-result messages."""
    results = []
    for tc in tool_calls:
        fn = tc.get("function", {})
        name = fn.get("name", "")
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        output = tool_registry.execute_tool(name, args)
        results.append(
            {
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "name": name,
                "content": output,
            }
        )
    return results


def _stream_text(text: str, chunk_size: int = 24) -> Generator[str, None, None]:
    """Yield text in small chunks (simulated streaming for UX)."""
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]


def stream_chat(session_id: str, user_message: str) -> Generator[str, None, None]:
    """Stream SSE-ready JSON deltas for a chat turn.

    Yields strings, each a JSON object:
      {"type": "delta", "content": "..."}
      {"type": "tool", "name": "...", "output": "..."}
      {"type": "done", "assistant": "full text"}
      {"type": "error", "message": "..."}
    """
    db = _db()
    try:
        session = db.get(ChatSession, session_id)
        if not session:
            yield json.dumps({"type": "error", "message": "session not found"})
            return

        # Auto-title on first user message
        if db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count() == 0:
            session.title = user_message[:60]
            db.commit()

        _persist(db, session_id, "user", user_message)
        history = _history_messages(db, session_id)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
        tools = tool_registry.tool_schemas()

        final_text = ""
        for _ in range(MAX_TOOL_ITERATIONS):
            resp = llm_client.chat_once(messages, tools=tools)
            choices = resp.get("choices") or []
            if not choices:
                yield json.dumps({"type": "error", "message": "LLM returned no choices"})
                return
            message = choices[0].get("message") or {}

            tool_calls = _parse_tool_calls(message)
            if tool_calls:
                tool_msgs = _run_tool_calls(tool_calls)
                for tm in tool_msgs:
                    yield json.dumps(
                        {"type": "tool", "name": tm["name"], "output": tm["content"][:500]},
                        ensure_ascii=False,
                    )
                messages.extend(tool_msgs)
                continue

            # Final text answer
            final_text = (message.get("content") or "").strip()
            for chunk in _stream_text(final_text):
                yield json.dumps({"type": "delta", "content": chunk}, ensure_ascii=False)
            break

        # Persist assistant message
        if final_text:
            _persist(db, session_id, "assistant", final_text)
            _touch_session(db, session_id)

        yield json.dumps({"type": "done", "assistant": final_text}, ensure_ascii=False)
    except llm_client.LLMError as e:
        yield json.dumps({"type": "error", "message": str(e)})
    except Exception as e:  # noqa: BLE001
        yield json.dumps({"type": "error", "message": f"chat failed: {e}"})
    finally:
        db.close()
