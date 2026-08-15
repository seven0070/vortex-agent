#!/usr/bin/env python3
"""
Vortex Agent CLI — talk to the Vortex backend API (localhost:8000).

Zero-dependency: stdlib only (argparse, urllib, json). Works on any Python 3.8+.

Usage:
    python vortex.py status
    python vortex.py chat "hello"
    python vortex.py agents
    python vortex.py task <task_id>
    ...

Or install as a command:
    pip install -e .   (see pyproject.toml)  ->  vortex status
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime

DEFAULT_HOST = "http://localhost:8000"
PREFIX = "/api/v1"
TIMEOUT = 60


# ----------------------------------------------------------------------
# HTTP helpers
# ----------------------------------------------------------------------
class ApiError(Exception):
    pass


def _request(method: str, path: str, payload=None, host: str = DEFAULT_HOST, raw: bool = False):
    url = host + PREFIX + path
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return body if raw else json.loads(body)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise ApiError(f"HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise ApiError(f"Cannot reach {host} — is the backend running? ({e.reason})") from e


def _get(path, host=DEFAULT_HOST, **kw):
    return _request("GET", path, host=host, **kw)


def _post(path, payload, host=DEFAULT_HOST, **kw):
    return _request("POST", path, payload=payload, host=host, **kw)


def _put(path, payload, host=DEFAULT_HOST, **kw):
    return _request("PUT", path, payload=payload, host=host, **kw)


def _dump(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


# ----------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------
def cmd_status(args):
    try:
        health = _get("/health", host=args.host)
        print(f"✅ Vortex backend: {health.get('status', '?')} (v{health.get('version', '?')})")
    except ApiError as e:
        print(f"❌ {e}")
        sys.exit(1)


def cmd_agents(args):
    data = _get(f"/agents?user_id={args.user_id}", host=args.host)
    _dump(data)


def cmd_chat(args):
    payload = {"user_id": args.user_id, "message": args.message}
    if args.agent_id:
        payload["agent_id"] = args.agent_id
    _dump(_post("/chat", payload, host=args.host))


def cmd_orchestrate(args):
    _dump(_post("/orchestrate", {"goal": args.goal}, host=args.host))


def cmd_task(args):
    _dump(_get(f"/tasks/{args.task_id}", host=args.host))


def cmd_council(args):
    _dump(_post("/council/deliberate", {"topic": args.topic}, host=args.host))


def cmd_memory(args):
    if args.action == "add":
        _dump(_post("/memory/add", {"content": args.content}, host=args.host))
    elif args.action == "recall":
        _dump(_post("/memory/recall", {"query": args.query}, host=args.host))
    elif args.action == "context":
        _dump(_get("/memory/context", host=args.host))


def cmd_graph(args):
    if args.action == "nodes":
        _dump(_get("/graph/nodes", host=args.host))
    elif args.action == "node":
        _dump(_post("/graph/nodes", {"id": args.node_id}, host=args.host))
    elif args.action == "edge":
        _dump(_post("/graph/edges", {"source": args.source, "target": args.target}, host=args.host))
    elif args.action == "neighbors":
        _dump(_get(f"/graph/neighbors?node_id={args.node_id}", host=args.host))


def cmd_governance(args):
    if args.action == "check":
        _dump(_post("/governance/check", {"action": args.action_desc or args.action}, host=args.host))
    elif args.action == "logs":
        _dump(_get("/governance/logs", host=args.host))


def cmd_sovereign(args):
    if args.action == "status":
        _dump(_get("/sovereign/status", host=args.host))
    elif args.action == "objectives":
        _dump(_post("/sovereign/objectives", {"objectives": args.objectives}, host=args.host))


def cmd_tools(args):
    if args.action == "list":
        _dump(_get("/tools", host=args.host))
    elif args.action == "run":
        _dump(_post("/tools/execute", {"tool": args.tool, "args": args.tool_args or {}}, host=args.host))


def cmd_evolution(args):
    if args.action == "propose":
        _dump(_post("/evolution/propose", {"description": args.description}, host=args.host))
    elif args.action == "candidates":
        _dump(_get("/evolution/candidates", host=args.host))


def cmd_benchmarks(args):
    _dump(_get("/benchmarks", host=args.host))


def cmd_trace(args):
    _dump(_get(f"/observability/trace?task_id={args.task_id}", host=args.host))


def cmd_config(args):
    if args.action == "list":
        _dump(_get("/settings", host=args.host))
    elif args.action == "get":
        data = _get("/settings", host=args.host)
        key = args.key
        settings = data.get("settings", {})
        if key not in settings:
            print(f"❌ Unknown setting '{key}'. Known: {', '.join(settings.keys())}", file=sys.stderr)
            sys.exit(1)
        print(f"{key} = {settings[key]}")
    elif args.action == "set":
        _dump(_put("/settings", {args.key: _coerce(args.value)}, host=args.host))
    elif args.action == "health":
        _dump(_get("/settings/health", host=args.host))


def _coerce(value: str):
    """Best-effort JSON coercion: true/false/null/numbers stay typed."""
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "none"):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def cmd_improve(args):
    payload = {}
    if args.hypothesis:
        payload["hypothesis"] = args.hypothesis
    _dump(_post("/settings/improve", payload, host=args.host))


# ----------------------------------------------------------------------
# Argument parser
# ----------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(
        prog="vortex",
        description="Vortex Agent CLI — control the autonomous agent platform from your terminal.",
    )
    p.add_argument("--host", default=DEFAULT_HOST, help=f"Backend base URL (default {DEFAULT_HOST})")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Check backend health")

    sub.add_parser("agents", help="List agents").add_argument("--user-id", default="cli-user")

    chat = sub.add_parser("chat", help="Send a chat message")
    chat.add_argument("message")
    chat.add_argument("--user-id", default="cli-user")
    chat.add_argument("--agent-id", default=None)

    orch = sub.add_parser("orchestrate", help="Run a multi-agent goal")
    orch.add_argument("goal")

    task = sub.add_parser("task", help="Get task status by ID")
    task.add_argument("task_id")

    council = sub.add_parser("council", help="Ask the agent council to deliberate")
    council.add_argument("topic")

    mem = sub.add_parser("memory", help="Memory operations")
    mem_sub = mem.add_subparsers(dest="action", required=True)
    mem_add = mem_sub.add_parser("add")
    mem_add.add_argument("content")
    mem_recall = mem_sub.add_parser("recall")
    mem_recall.add_argument("query")
    mem_sub.add_parser("context")

    graph = sub.add_parser("graph", help="Knowledge graph operations")
    graph_sub = graph.add_subparsers(dest="action", required=True)
    graph_sub.add_parser("nodes")
    graph_node = graph_sub.add_parser("node")
    graph_node.add_argument("node_id")
    graph_edge = graph_sub.add_parser("edge")
    graph_edge.add_argument("source")
    graph_edge.add_argument("target")
    graph_nei = graph_sub.add_parser("neighbors")
    graph_nei.add_argument("node_id")

    gov = sub.add_parser("governance", help="Governance checks and logs")
    gov_sub = gov.add_subparsers(dest="action", required=True)
    gov_check = gov_sub.add_parser("check")
    gov_check.add_argument("action_desc", nargs="?")
    gov_sub.add_parser("logs")

    sov = sub.add_parser("sovereign", help="Sovereign engine status/objectives")
    sov_sub = sov.add_subparsers(dest="action", required=True)
    sov_sub.add_parser("status")
    sov_obj = sov_sub.add_parser("objectives")
    sov_obj.add_argument("objectives", nargs="+")

    tools = sub.add_parser("tools", help="Tool registry operations")
    tools_sub = tools.add_subparsers(dest="action", required=True)
    tools_sub.add_parser("list")
    tools_run = tools_sub.add_parser("run")
    tools_run.add_argument("tool")
    tools_run.add_argument("--arg", dest="tool_args", action="append", default=[],
                          help="key=value pairs passed as tool args (repeatable)")

    evo = sub.add_parser("evolution", help="Evolution engine")
    evo_sub = evo.add_subparsers(dest="action", required=True)
    evo_prop = evo_sub.add_parser("propose")
    evo_prop.add_argument("description")
    evo_sub.add_parser("candidates")

    sub.add_parser("benchmarks", help="Show benchmark results")

    trace = sub.add_parser("trace", help="Observability trace for a task")
    trace.add_argument("task_id")

    conf = sub.add_parser("config", help="View/change runtime settings")
    conf_sub = conf.add_subparsers(dest="action", required=True)
    conf_sub.add_parser("list", help="Show all effective settings")
    conf_get = conf_sub.add_parser("get")
    conf_get.add_argument("key")
    conf_set = conf_sub.add_parser("set")
    conf_set.add_argument("key")
    conf_set.add_argument("value")
    conf_sub.add_parser("health", help="LLM connectivity + config summary")

    improve = sub.add_parser("improve", help="Self-audit + propose improvements (EvolutionEngine)")
    improve.add_argument("--hypothesis", default=None, help="Custom improvement idea")

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    cmd = args.command

    # Convert --arg key=value pairs into a dict for tools run
    if cmd == "tools" and args.action == "run":
        kv = {}
        for item in args.tool_args:
            if "=" in item:
                k, v = item.split("=", 1)
                kv[k] = v
        args.tool_args = kv

    try:
        globals()[f"cmd_{cmd}"](args)
    except ApiError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
