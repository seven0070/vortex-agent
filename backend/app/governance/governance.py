"""Governance layer – policy enforcement and audit logging."""

import json
from pathlib import Path
from typing import List, Dict, Any

from sqlalchemy.orm import Session
from ..models import GovernanceLog, SessionLocal

# ----------------------------------------------------------------------
# Policy definition
# ----------------------------------------------------------------------
# The policy file is stored under $VORTEX_HOME/policy.json.
# It maps an operation type (e.g. "file_write", "shell_exec") to a list of
# allowed resource patterns (glob or regex) and a required permission level.
# Example:
# {
#   "file_write": {
#       "max_risk": "low",                     # low / medium / high
#       "allowed_paths": ["./data/.*", "/tmp/.*"]
#   },
#   "shell_exec": {
#       "max_risk": "medium",
#       "allowed_commands": ["ls", "cat", "grep"]
#   }
# }
# ----------------------------------------------------------------------


POLICY_FILE = Path("/c/Users/sanath/vortex-agent/backend/../policy.json")  # adjust as needed


def _load_policy() -> Dict[str, Any]:
    if POLICY_FILE.is_file():
        return json.loads(POLICY_FILE.read_text())
    # If no policy file exists, load a minimal safe default
    return {
        "file_write": {"max_risk": "low", "allowed_paths": [".*/tmp/.*"]},
        "shell_exec": {"max_risk": "medium", "allowed_commands": ["echo", "ls", "cat", "grep"]},
        "network": {"max_risk": "high", "allowed_domains": ["localhost", "127.0.0.1"]},
        # Extend with more operation types as needed
    }


POLICY = _load_policy()


class GovernanceEngine:
    """
    Central enforcement point for sensitive operations.

    All high‑risk actions (file writes, shell commands, network calls,
    code deployment, self‑modification) must pass through this class.
    It evaluates the policy, records the decision, and returns either
    "ALLOW", "DENY", or "ESCALATE".
    """

    def __init__(self, db: Session):
        self.db = db
        # Compile policy for quicker checks
        self._compile_policy()

    # ------------------------------------------------------------------
    # Policy compilation – turns human‑readable patterns into utilities
    # ------------------------------------------------------------------
    def _compile_policy(self) -> None:
        """
        Pre‑process the raw policy dict into structures that can be used
        for fast matching (e.g., compile regexes, build path_matchers).
        This method is called once at initialization.
        """
        self._path_matchers = {}
        self._command_allowlist = {}
        self._domain_allowlist = {}

        for op_type, spec in POLICY.items():
            max_risk = spec.get("max_risk", "low")
            # Risk hierarchy – lower index means higher risk
            self.risk_level = {"low": 2, "medium": 1, "high": 0}

            if "allowed_paths" in spec:
                self._path_matchers[op_type] = [
                    self._compile_glob(p) for p in spec["allowed_paths"]
                ]

            if "allowed_commands" in spec:
                self._command_allowlist[op_type] = set(spec["allowed_commands"])

            if "allowed_domains" in spec:
                self._domain_allowlist[op_type] = set(spec["allowed_domains"])

    @staticmethod
    def _compile_glob(glob_pat: str) -> callable:
        """
        Convert a shell‑style glob pattern into a callable that matches
        against a full path string.
        """
        import fnmatch, re

        # Simple fnmatch → regex conversion (supports * ? [..] [])
        regex_pat = "^" + re.escape(glob_pat).replace("\\*", ".*").replace("\\?", ".").replace("\\[", "[").replace("\\]", "]") + "$"
        return re.compile(regex_pat).match

    # ------------------------------------------------------------------
    # Core decision logic
    # ------------------------------------------------------------------
    def is_allowed(self, operation: str, resource: str, requester: str) -> str:
        """
        Determine whether an operation is permitted.

        Parameters
        ----------
        operation: str
            The type of action (e.g. "file_write", "shell_exec").
        resource: str
            The target/resource the operation acts upon (e.g. a file path,
            a shell command string, a host/port).
        requester: str
            Identifier of the calling agent (often the agent_id).

        Returns
        -------
        str
            One of "ALLOW", "DENY", or "ESCALATE".
        """
        # 1️⃣ Look up policy entry
        spec = POLICY.get(operation)
        if not spec:
            # Unknown operation is considered high‑risk → deny
            self._log_decision(
                operation=operation,
                decision="DENY",
                rationale="No policy entry for operation",
                requested_by=requester,
            )
            return "DENY"

        # 2️⃣ Risk‑based gating
        max_risk = spec.get("max_risk", "low")
        risk_index = {"low": 2, "medium": 1, "high": 0}[max_risk]

        # Higher‑risk operations are subject to stricter checks
        # (e.g., network operations always require explicit allowlist)
        if operation == "network" and risk_index < 1:
            # If risk is not high (0) but operation is network, enforce domain check
            if not self._is_domain_allowed(resource):
                self._log_decision(
                    operation=operation,
                    decision="DENY",
                    rationale="Domain not in allowed list",
                    requested_by=requester,
                )
                return "DENY"

        # 3️⃣ Operation‑specific validation
        if operation == "file_write":
            if not self._path_allowed(resource):
                self._log_decision(
                    operation=operation,
                    decision="DENY",
                    rationale="Path not permitted",
                    requested_by=requester,
                )
                return "DENY"
        elif operation == "shell_exec":
            if not self._command_allowed(resource):
                self._log_decision(
                    operation=operation,
                    decision="DENY",
                    rationale="Command not in allowlist",
                    requested_by=requester,
                )
                return "DENY"
        elif operation == "network":
            if not self._domain_allowed(resource):
                self._log_decision(
                    operation=operation,
                    decision="DENY",
                    rationale="Domain not allowed",
                    requested_by=requester,
                )
                return "DENY"

        # 4️⃣ All checks passed → allow
        self._log_decision(
            operation=operation,
            decision="ALLOW",
            rationale="Policy check passed",
            requested_by=requester,
        )
        return "ALLOW"

    # ------------------------------------------------------------------
    # Helper matchers
    # ------------------------------------------------------------------
    @staticmethod
    def _glob_to_regex(glob: str) -> str:
        import re

        return "^" + re.escape(glob).replace("\\*", ".*").replace("\\?", ".") + "$"

    def _path_allowed(self, path: str) -> bool:
        """Check if a filesystem path matches any allowed_glob from policy."""
        for matcher in self._path_matchers.get("file_write", []):
            if matcher(path):
                return True
        return False

    def _command_allowed(self, cmd: str) -> bool:
        """Check if a shell command is present in the allowlist."""
        allowed = self._command_allowlist.get("shell_exec", set())
        # Simple tokenization – split on whitespace and compare first token
        first_token = cmd.strip().split()[0] if cmd.strip() else ""
        return first_token in allowed

    def _domain_allowed(self, domain: str) -> bool:
        """Check if a network domain matches any allowed_domains."""
        allowed = self._domain_allowlist.get("network", set())
        return domain.lower() in allowed

    # ------------------------------------------------------------------
    # Auditing
    # ------------------------------------------------------------------
    def _log_decision(
        self,
        operation: str,
        decision: str,
        rationale: str,
        requested_by: str,
        extra: Dict[str, Any] | None = None,
        resource: str | None = None,
    ) -> None:
        """
        Persist a governance decision record.
        ``extra`` can hold additional context (e.g., resource path).
        ``resource`` is stored directly (column is NOT NULL — fall back to operation).
        """
        log = GovernanceLog(
            operation=operation,
            resource=resource or operation,
            decision=decision,
            rationale=rationale,
            requested_by=requested_by,
        )
        if extra:
            # Store free‑form extra context as JSON in rationale for simplicity
            log.rationale += f" | extra={extra}"
        self.db.add(log)
        self.db.commit()

    # ------------------------------------------------------------------
    # Public convenience wrappers
    # ------------------------------------------------------------------
    def allow(self, operation: str, resource: str, requester: str) -> bool:
        return self.is_allowed(operation, resource, requester) == "ALLOW"

    def deny(self, operation: str, resource: str, requester: str) -> bool:
        return self.is_allowed(operation, resource, requester) == "DENY"

    def escalate(self, operation: str, resource: str, requester: str) -> bool:
        return self.is_allowed(operation, resource, requester) == "ESCALATE"