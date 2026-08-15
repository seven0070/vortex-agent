"""Observability – tracing and structured logging."""

from __future__ import annotations
import uuid
import time
import contextvars
from typing import Optional, Dict, Any

# ----------------------------------------------------------------------
# Context variables for trace propagation
# ----------------------------------------------------------------------
_trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("trace_id", default=None)
_span_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("span_id", default=None)


def start_trace(*, task_id: Optional[str] = None) -> str:
    """
    Begin a new trace. Returns the trace_id.
    Should be called once at the entry point of a user request / task.
    """
    trace_id = str(uuid.uuid4())
    _trace_id_var.set(trace_id)
    _span_id_var.set(str(uuid.uuid4()))
    # In a full implementation, emit a structured log entry here
    print(f"[TRACE START] trace_id={trace_id} task_id={task_id}")
    return trace_id


def end_trace(*, outcome: str = "success", error: Optional[str] = None) -> None:
    """
    Close the current trace.
    """
    trace_id = _trace_id_var.get()
    print(f"[TRACE END] trace_id={trace_id} outcome={outcome} error={error}")
    _trace_id_var.set(None)
    _span_id_var.set(None)


def current_trace_id() -> Optional[str]:
    return _trace_id_var.get()


def current_span_id() -> Optional[str]:
    return _span_id_var.get()


class Span:
    """
    Context-manager for a nested span within a trace.
    Usage:
        with Span("tool_call", tool="shell_exec") as span:
            result = do_work()
            span.set_attribute("latency_ms", 123)
    """

    def __init__(self, name: str, **attributes: Any) -> None:
        self.name = name
        self.attributes = attributes
        self.start_time = time.perf_counter()
        self.span_id = str(uuid.uuid4())
        self.parent_span_id = _span_id_var.get()
        _span_id_var.set(self.span_id)

    def __enter__(self) -> "Span":
        print(
            f"[SPAN START] trace_id={current_trace_id()} span_id={self.span_id} "
            f"parent={self.parent_span_id} name={self.name} attrs={self.attributes}"
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration_ms = int((time.perf_counter() - self.start_time) * 1000)
        outcome = "error" if exc_type else "success"
        print(
            f"[SPAN END] trace_id={current_trace_id()} span_id={self.span_id} "
            f"name={self.name} duration_ms={duration_ms} outcome={outcome}"
        )
        _span_id_var.set(self.parent_span_id)

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value


# ----------------------------------------------------------------------
# Structured event logging (can be swapped for OpenTelemetry, etc.)
# ----------------------------------------------------------------------
def log_event(event_type: str, payload: Dict[str, Any]) -> None:
    """Emit a structured event with trace context."""
    trace_id = current_trace_id()
    span_id = current_span_id()
    record = {
        "timestamp": time.time(),
        "trace_id": trace_id,
        "span_id": span_id,
        "event": event_type,
        **payload,
    }
    # In production, send to a collector / file / stdout as JSON
    print(f"[EVENT] {record}")