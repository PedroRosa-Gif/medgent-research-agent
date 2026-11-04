# Roadmap & Deferred Decisions

Living document tracking build phases and decisions deliberately deferred to a
later task, so nothing gets lost between sessions.

## Deferred / parked work

### 🐳 Docker & containerization (parked — dedicated task)
- Decided to run **Ollama via Docker** (not a native install), since it keeps the
  dev machine clean and matches the user's workflow.
- A dedicated containerization task will add a root `docker-compose.yml` with:
  - an `ollama/ollama` service exposing port `11434`;
  - a **named volume** persisting pulled models (models live in the volume, NOT in
    the image and NOT in the git repo — the image only ships the Ollama server);
  - later, the backend (FastAPI) and frontend services in the same compose stack.
- The `OllamaAdapter` should read the base URL from settings
  (e.g. `OLLAMA_BASE_URL`, default `http://localhost:11434`) so it points at the
  container without code changes.
- Not required for Task 3: LLM-provider tests are fully mocked and need neither
  Docker nor a running Ollama.

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
- [ ] Task 3 — LLM provider abstraction (port + Ollama adapter + Groq/Gemini stubs)
- [ ] Task 4 — PubMed retrieval tool (structured retrieval)
- [ ] Task 5 — Web search tool + common retrieval interface
- [ ] Task 6 — planner + fetch_evidence nodes
- [ ] Task 7 — evaluator node (heuristics + structured extraction + score)
- [ ] Task 8 — refine_queries + graph assembly (conditional routing + checkpointer)
- [ ] Task 9 — synthesizer node + end-to-end CLI
- [ ] Task 10 — React single-page reasoning UI (+ FastAPI/SSE)
- [ ] Task 11 — optional LangSmith observability + polish
- [ ] Docker/containerization (parked — see above)
