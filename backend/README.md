# MedGent backend

Hexagonal (ports & adapters) Python backend for the MedGent Research Agent.

## Layout

```
src/medgent/
├── domain/        # pure business logic, zero framework imports
├── application/   # use cases, LangGraph orchestration, ports (interfaces)
│   ├── ports/
│   ├── use_cases/
│   └── graph/
└── adapters/      # concrete implementations
    ├── driving/   # inbound: FastAPI / CLI
    └── driven/    # outbound: PubMed, web, LLM providers, checkpointer
```

Dependency rule: adapters → application → domain. The domain never imports the
application or adapters; the application never imports adapters.

## Development

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync                      # install deps (incl. dev group)
uv run ruff check .          # lint
uv run ruff format --check . # formatting
uv run pytest                # tests
```

Copy `.env.example` to `.env` and adjust as needed.

### Configuration (env vars)

All optional — the app boots on local Ollama with no keys. Set them in `.env`:

| Var | Default | Purpose |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `ollama` | `ollama` (real) · `groq`/`gemini` (stubs) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen2.5:7b` | model name |
| `GROQ_API_KEY` / `GEMINI_API_KEY` | — | for the (future) hosted providers |
| `NCBI_API_KEY` | — | raises PubMed/Entrez rate limits |
| `LANGSMITH_API_KEY` | — | reserved for tracing (not yet wired) |
| `CORS_ORIGINS` | Vite dev origins | JSON array of allowed browser origins |

## Running it

Both entry points are driving adapters over the same `ResearchTopicUseCase`.

**CLI:**

```bash
./run.ps1 "efficacy of metformin for type 2 diabetes"   # Windows wrapper
# cross-platform: PYTHONPATH=src uv run python -m medgent "<topic>"
# flags: --max-iterations --provider --model --no-save --output-dir
#        --max-papers --max-studies --batch-size
```

**HTTP API** (serves `http://localhost:8000`):

```bash
./serve.ps1                 # Windows wrapper
# cross-platform: PYTHONPATH=src uv run uvicorn \
#   medgent.adapters.driving.api.app:create_app --factory --port 8000
```

Endpoints: `GET /health`, `POST /research` (sync JSON), `GET /research/stream`
(SSE — `node_start`/`step`/`token`/`done`/`error`). See the SSE contract in
[`../docs/architecture.md`](../docs/architecture.md) §6.

> **Windows note:** the `run.ps1`/`serve.ps1` wrappers set `PYTHONPATH=src` to work
> around a CPython `.pth` encoding bug on non-ASCII home paths. See
> [`../docs/running-locally.md`](../docs/running-locally.md) troubleshooting.

## Local LLM (Ollama)

The default provider is a local Ollama server run via Docker (GPU-accelerated).
Bring it up with `docker compose up -d` from the repo root (it auto-pulls the
model). Full walkthrough, incl. the GPU-vs-CPU caveat:
[`../docs/running-locally.md`](../docs/running-locally.md).
