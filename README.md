 ![Alt text](https://github.com/seven0070/vortex-agent/blob/30a9324caba88b88902d4555294977788a4d57e7/blackhole.png)

# Vortex Agent

Autonomous, local-first AI agent platform with a council of specialized agents, persistent memory, knowledge graph, governance engine, and sovereign self-management.

## Architecture

```
vortex-agent/
├── backend/                 # FastAPI backend (Python)
│   └── app/
│       ├── main.py          # App entry: CORS, router mounting
│       ├── models.py        # SQLAlchemy models (User, Agent, Task, Memory, Graph, ...)
│       ├── api/v1/          # HTTP endpoints (prefix /api/v1)
│       ├── core/            # memory_system, orchestration
│       ├── council/         # multi-agent deliberation
│       ├── governance/      # policy compliance checks
│       ├── sovereign/       # self-management engine
│       ├── knowledge/       # knowledge graph
│       ├── evolution/       # improvement proposals
│       ├── tools/           # tool registry
│       └── observability/   # tracing
├── frontend/                # React 18 + Vite + Tauri 2 desktop app
│   └── src-tauri/           # Rust shell (com.vortex.agent)
├── cli.py                   # Zero-dependency CLI (stdlib only)
└── run_backend.py           # Start backend on :8000 (uvicorn, reload)
```

## Quick Start

### Backend

```bash
python run_backend.py          # serves http://localhost:8000
curl http://localhost:8000/api/v1/health
```

### CLI

Zero-dependency — uses only Python stdlib (`argparse` + `urllib`). Point it at the backend with `--host` (default `http://localhost:8000`).

```bash
python cli.py status                     # backend health
python cli.py agents                     # list agents
python cli.py chat "summarize today"     # chat message
python cli.py orchestrate "goal text"    # multi-agent goal
python cli.py task <task_id>             # task status
python cli.py council "topic"            # council deliberation
python cli.py memory add "note"          # store memory
python cli.py memory recall "query"      # recall memory
python cli.py memory context             # full memory context
python cli.py graph nodes                # knowledge graph nodes
python cli.py graph neighbors <id>       # graph neighbors
python cli.py governance check "action"  # compliance check
python cli.py governance logs            # governance log
python cli.py sovereign status           # sovereign state
python cli.py sovereign objectives a b   # set objectives
python cli.py tools list                 # tool registry
python cli.py tools run <tool> --arg k=v # execute tool
python cli.py evolution propose "idea"   # evolution proposal
python cli.py evolution candidates       # pending candidates
python cli.py benchmarks                 # benchmark results
python cli.py trace <task_id>            # observability trace
```

### Desktop App

```bash
cd frontend
npm install
npm run tauri:build        # produces MSI + NSIS + standalone exe
```

## API Surface

All endpoints under `/api/v1` (the router declares the prefix itself — do not add it again in `include_router`):

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| POST | `/chat` | Chat message |
| POST | `/orchestrate` | Multi-agent orchestration |
| GET | `/tasks/{task_id}` | Task status |
| POST | `/council/deliberate` | Council deliberation |
| POST | `/memory/add`, `/memory/recall` | Memory store/recall |
| GET | `/memory/context` | Full memory context |
| POST/GET | `/graph/nodes`, `/graph/edges`, `/graph/neighbors` | Knowledge graph |
| POST | `/governance/check` | Compliance check |
| GET | `/governance/logs` | Governance log |
| GET | `/sovereign/status` | Sovereign status |
| POST | `/sovereign/objectives` | Set objectives |
| GET | `/tools`, POST `/tools/execute` | Tool registry |
| POST | `/evolution/propose`, GET `/evolution/candidates` | Evolution |
| GET | `/benchmarks` | Benchmarks |
| GET | `/observability/trace` | Trace |

## Known Notes

- **Workspace isolation**: `src-tauri/Cargo.toml` declares its own `[workspace]` root so Cargo does not inherit a parent-directory workspace (`~/Cargo.toml`) that may reference uncloned submodules.
- **Data**: SQLite via SQLAlchemy; `VORTEX_HOME` env var overrides the data directory (default `backend/vortex-data/`).
