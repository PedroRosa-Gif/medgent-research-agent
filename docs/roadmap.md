# Roadmap & Deferred Decisions

Living document tracking build phases and decisions deliberately deferred to a
later task, so nothing gets lost between sessions.

## Done / previously parked

### 🐳 Docker & containerization — Ollama part DONE
- Decided to run **Ollama via Docker** (not a native install), since it keeps the
  dev machine clean and matches the user's workflow.
- **Done (Task 9):** a root `docker-compose.yml` with:
  - an `ollama/ollama` service exposing port `11434`;
  - a **named volume** (`ollama_data`) persisting pulled models — models live in the
    volume, NOT in the image and NOT in the git repo;
  - an `ollama-init` one-shot service that waits for the server to be healthy and
    **auto-pulls the model** (`OLLAMA_MODEL`, default `qwen2.5:7b`), so a plain
    `docker compose up` ends with the model present.
  - See [`running-locally.md`](running-locally.md) for the walkthrough and
    `scripts/smoke_ollama.py` for a manual end-to-end check.
- The `OllamaAdapter` already reads the base URL from settings
  (`OLLAMA_BASE_URL`, default `http://localhost:11434`), so it points at the
  container without code changes — the Docker work touched no production Python.
- **Still future:** bringing the **backend (FastAPI) and frontend** into the same
  compose stack. That ships alongside the API/UI tasks, not here.

## Deferred / parked work

### LLM providers (partial by design)
- Task 3 implements the **Ollama adapter for real**; **Groq** and **Gemini** are
  explicit stubs behind the same `LLMPort`, to be implemented when needed.

## Documentation debt
- `docs/architecture.md` on disk is still the ORIGINAL draft (mentions ReAct,
  LocalRAGTool, Streamlit). The revised architecture (hexagonal, React/FastAPI/SSE,
  provider abstraction) was written during planning but appears NOT to have been
  merged. Needs reconciliation in a follow-up — flagged to the user.

## Build phases (high level)
- [x] Task 1 — Backend scaffolding (hexagonal, uv, ruff, pytest, CI)
- [x] Task 2 — Agent state + Pydantic schemas (domain)
- [x] Task 3 — LLM provider abstraction (port + Ollama adapter + Groq/Gemini stubs)
- [x] Task 4 — PubMed retrieval tool (structured retrieval)
- [x] Task 5 — Web search tool + common retrieval interface
- [x] Task 6 — planner + fetch_evidence nodes
- [x] Task 7 — evaluator node (heuristics + structured extraction + score)
- [x] Task 8 — refine_queries + graph assembly (conditional routing + checkpointer)
- [x] Task 9 — Docker + Ollama local LLM infrastructure (compose + auto model pull)
- [ ] Task 10 — synthesizer node + end-to-end CLI ← **next**
- [ ] Task 11 — React single-page reasoning UI (+ FastAPI/SSE)
- [ ] Task 12 — optional LangSmith observability + polish
- [ ] Future — containerize backend + frontend into the same compose stack
