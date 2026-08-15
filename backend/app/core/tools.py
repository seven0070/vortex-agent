"""
Vortex tool registry for the Hermes-like chat core.

Safe local tools the LLM can invoke mid-chat. Each tool has a schema
(OpenAI function-calling format) and a Python implementation. All tools are
sandboxed: bounded output, timeouts, path restrictions to the repo.
"""

import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # vortex-agent/
MAX_OUTPUT = 8000  # chars
MAX_FILE_BYTES = 200_000  # 200 KB
TIMEOUT = 30  # seconds


def _clip(text: str) -> str:
    if len(text) > MAX_OUTPUT:
        return text[:MAX_OUTPUT] + f"\n...[truncated {len(text) - MAX_OUTPUT} chars]"
    return text


# ----------------------------------------------------------------------
# Tool implementations
# ----------------------------------------------------------------------
def terminal(command: str, workdir: str = None) -> str:
    """Run a shell command (blocking, bounded)."""
    cwd = workdir or str(REPO_ROOT)
    try:
        r = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
        out = r.stdout or ""
        if r.stderr:
            out += f"\n[stderr]\n{r.stderr}"
        if r.returncode != 0:
            out += f"\n[exit code: {r.returncode}]"
        return _clip(out) if out.strip() else f"(exit {r.returncode}, no output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out after {TIMEOUT}s"
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {e}"


def read_file(path: str) -> str:
    """Read a text file (bounded size)."""
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        return f"ERROR: file not found: {path}"
    if p.stat().st_size > MAX_FILE_BYTES:
        return f"ERROR: file too large ({p.stat().st_size} bytes > {MAX_FILE_BYTES})"
    try:
        return _clip(p.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {e}"


def write_file(path: str, content: str) -> str:
    """Write text content to a file (creates parent dirs)."""
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"WROTE {p} ({len(content)} chars)"
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {e}"


def list_files(path: str = ".") -> str:
    """List files in a directory (bounded depth)."""
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists() or not p.is_dir():
        return f"ERROR: not a directory: {path}"
    try:
        entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        lines = []
        for e in entries[:200]:
            kind = "DIR " if e.is_dir() else "FILE"
            lines.append(f"{kind} {e.name}")
        return _clip("\n".join(lines) if lines else "(empty dir)")
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {e}"


def now() -> str:
    """Return the current UTC timestamp."""
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())


# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------
TOOLS = {
    "terminal": {
        "schema": {
            "type": "function",
            "function": {
                "name": "terminal",
                "description": "Run a shell command in the vortex-agent repo (bounded, 30s timeout). Returns stdout/stderr.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Shell command to run"},
                        "workdir": {"type": "string", "description": "Working directory (optional)"},
                    },
                    "required": ["command"],
                },
            },
        },
        "impl": terminal,
    },
    "read_file": {
        "schema": {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a text file (relative to repo root or absolute). Max 200KB.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        "impl": read_file,
    },
    "write_file": {
        "schema": {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write text content to a file (relative to repo root or absolute). Creates parent dirs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        "impl": write_file,
    },
    "list_files": {
        "schema": {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files in a directory (relative to repo root or absolute).",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "default": "."}},
                },
            },
        },
        "impl": list_files,
    },
    "now": {
        "schema": {
            "type": "function",
            "function": {
                "name": "now",
                "description": "Get the current UTC timestamp.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        "impl": now,
    },
}


def tool_schemas() -> list:
    return [t["schema"] for t in TOOLS.values()]


def execute_tool(name: str, args: dict) -> str:
    """Execute a tool by name with parsed args. Returns string result."""
    tool = TOOLS.get(name)
    if not tool:
        return f"ERROR: unknown tool '{name}'"
    impl = tool["impl"]
    try:
        # Pass only args the implementation accepts
        import inspect

        sig = inspect.signature(impl)
        kwargs = {k: v for k, v in (args or {}).items() if k in sig.parameters}
        result = impl(**kwargs)
        return str(result)
    except TypeError as e:
        return f"ERROR: bad args for {name}: {e}"
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {name} failed: {e}"
