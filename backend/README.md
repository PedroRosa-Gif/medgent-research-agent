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
