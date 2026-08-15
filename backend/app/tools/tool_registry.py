"""Tool Registry – standardized capability system with governance integration."""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from ..governance.governance import GovernanceEngine


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ToolSpec:
    """Declarative description of a tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]      # JSON Schema
    output_schema: Dict[str, Any]     # JSON Schema
    permissions: List[str]            # e.g. ["file_write", "shell_exec"]
    risk_level: RiskLevel
    timeout_seconds: int = 30
    rollback: Optional[Callable[..., Any]] = None  # optional callable to undo


class ToolRegistry:
    """
    Central registry of all available tools.
    Handles lookup, validation, and delegation to the actual implementation
    after Governance approval.
    """

    def __init__(self, governance: GovernanceEngine) -> None:
        self.governance = governance
        self._tools: Dict[str, ToolSpec] = {}
        self._implementations: Dict[str, Callable[..., Any]] = {}
        self._register_builtin_tools()

    # ------------------------------------------------------------------
    # Builtin tool registration (placeholder implementations)
    # ------------------------------------------------------------------
    def _register_builtin_tools(self) -> None:
        """Register a minimal set of tools for demonstration."""
        self.register(
            ToolSpec(
                name="local_file_write",
                description="Write text content to a local file path.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
                output_schema={"type": "object", "properties": {"success": {"type": "boolean"}}},
                permissions=["file_write"],
                risk_level=RiskLevel.LOW,
                timeout_seconds=5,
            ),
            lambda path, content: self._impl_local_file_write(path, content),
        )

        self.register(
            ToolSpec(
                name="shell_exec",
                description="Execute a shell command and return stdout/stderr.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "cwd": {"type": "string"},
                    },
                    "required": ["command"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "stdout": {"type": "string"},
                        "stderr": {"type": "string"},
                        "exit_code": {"type": "integer"},
                    },
                },
                permissions=["shell_exec"],
                risk_level=RiskLevel.MEDIUM,
                timeout_seconds=30,
            ),
            lambda command, cwd=None: self._impl_shell_exec(command, cwd),
        )

        # Add more tools here as needed...

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def register(self, spec: ToolSpec, implementation: Callable[..., Any]) -> None:
        """Add a tool to the registry."""
        if spec.name in self._tools:
            raise ValueError(f"Tool '{spec.name}' already registered")
        self._tools[spec.name] = spec
        self._implementations[spec.name] = implementation

    def get_spec(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def list_tools(self) -> List[ToolSpec]:
        return list(self._tools.values())

    def execute(
        self,
        tool_name: str,
        agent_id: str,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a tool after governance approval.

        Returns the tool's output dict, or raises an exception if denied / failed.
        """
        spec = self._tools.get(tool_name)
        if not spec:
            raise ValueError(f"Unknown tool: {tool_name}")

        # 1️⃣ Governance gate – check each required permission
        for perm in spec.permissions:
            # Resource string is synthesized from input_data for demo purposes
            resource = str(input_data)  # In reality, derive precise resource (e.g., file path)
            decision = self.governance.is_allowed(
                operation=perm,
                resource=resource,
                requester=agent_id,
            )
            if decision != "ALLOW":
                raise PermissionError(
                    f"Governance {decision} for permission '{perm}' on resource '{resource}'"
                )

        # 2️⃣ Execute the implementation
        impl = self._implementations[tool_name]
        try:
            result = impl(**input_data)
            return result
        except Exception as exc:
            # Could call spec.rollback here if defined
            raise RuntimeError(f"Tool '{tool_name}' execution failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Builtin implementations (extremely simplified)
    # ------------------------------------------------------------------
    @staticmethod
    def _impl_local_file_write(path: str, content: str) -> Dict[str, Any]:
        from pathlib import Path
        Path(path).write_text(content, encoding="utf-8")
        return {"success": True}

    @staticmethod
    def _impl_shell_exec(command: str, cwd: Optional[str] = None) -> Dict[str, Any]:
        import subprocess, shlex
        proc = subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=30,
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
        }


# ----------------------------------------------------------------------
# Factory
# ----------------------------------------------------------------------
def ToolRegistryFactory(db, governance: GovernanceEngine) -> ToolRegistry:
    return ToolRegistry(governance)