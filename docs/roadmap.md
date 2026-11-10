# Roadmap & Backlog

Living document: what was built, in order, and what is deliberately deferred.

## Build log (shipped)

- [x] **Task 1 — Backend scaffolding.** Hexagonal layout (`domain`/`application`/
  `adapters`), uv, ruff, pytest, GitHub Actions CI, `.gitattributes` for LF.
- [x] **Task 2 — Agent state + Pydantic schemas.** `AgentState` (TypedDict) holding
  Pydantic models (`Evidence`, `EvaluatedStudy`, `QueryPlan`, enums); pure domain.
- [x] **Task 3 — LLM provider abstraction.** `LLMPort` + `OllamaAdapter` (real) and
  `GroqAdapter`/`GeminiAdapter` stubs behind the same port; a `build_llm` factory.
- [x] **Task 4 — PubMed retrieval.** `EvidenceRetrievalPort` + `PubMedAdapter`
  (Entrez esearch/efetch via `requests`, retry/backoff, mocked tests).
- [x] **Task 5 — Web search + aggregation.** `WebSearchAdapter` (DuckDuckGo via
  `ddgs`) behind the same port + an `aggregate_evidence` multi-source helper.
- [x] **Task 6 — planner + fetch_evidence nodes.** DI factory closures depending on
  ports only.
- [x] **Task 7 — evaluator node.** Hybrid scoring: deterministic heuristics
  (domain) + structured LLM extraction + a code-computed `quality_score`.
- [x] **Task 8 — refine_queries + graph assembly.** `StateGraph` with conditional
  routing (the self-correction loop) compiled with a `MemorySaver` checkpointer.
- [x] **Task 9 — Docker + Ollama.** Root `docker-compose.yml`: server + one-shot
  auto model-pull, named volume, **NVIDIA GPU reservation enabled** (see caveat).
- [x] **Task 10 — synthesizer + CLI.** `synthesizer` node, `ResearchTopicUseCase`,
  and `python -m medgent "<topic>"` with terminal streaming + markdown file output.
- [x] **Task 11a — FastAPI SSE API.** `GET /health`, `POST /research` (sync), and
  `GET /research/stream` (SSE). Events: `node_start`, `step`, `token`, `done`,
  `error`. The sync generator runs off-thread so the event loop isn't blocked.
- [x] **Task 11b — React single-page UI.** SSE-driven reasoning timeline, token-
  streamed report, sources panel; pure reducer tested with Vitest.
- [x] **Reasoning UX + redesign.** Query cap (≤5) to kill a runaway-fetch slowdown;
  `node_start` events + "thinking" labels and rich result narration; centered,
  auto-scrolling layout; dark/light themes, glass surfaces, ambient glow, blueprint
  grid; minimalist medical-cross brand mark; GPU acceleration for Ollama.

## Backlog (not yet done)

### Code (planned for a follow-up PR, kept out of the docs PR)
- **Optional GPU compose override.** `docker-compose.yml` currently reserves an
  NVIDIA GPU unconditionally, so `docker compose up` fails on a machine without one
  (workaround today: comment out the `deploy:` block). Move the reservation to a
  `docker-compose.gpu.yml` override so the base file runs anywhere.
- **Frontend CI job.** CI runs the backend only. Add a job: `npm ci`, `lint`,
  `test`, `build`, `check:contrast`.
- **Implement Groq / Gemini adapters for real.** They are stubs. Groq's free tier
  (Llama 3.x) gives fast, high-quality runs without a local GPU — the best path for
  someone cloning without NVIDIA hardware.
- **API hardening.** `POST /research` / the SSE endpoint have no topic-length limit
  or concurrency guard; each request drives an LLM + external calls. Add bounds
  before any public deployment.
- **UI "Stop" truly cancels.** The browser stops listening, but the backend run
  continues in its worker thread (and keeps using the GPU) until it finishes.
- **Query/source separation.** Planner queries use PubMed/MeSH syntax (`AND`, …)
  that goes verbatim to web search, hurting web results. Tailor per source.

### Larger / future
- **LangSmith tracing.** Only the `langsmith_api_key` setting exists; wire actual
  tracing, enabled when the key is present.
- **Persistent checkpointer (SQLite).** `MemorySaver` loses state on restart.
  SQLite persistence unlocks the **conversational follow-up mode** (resume a
  `thread_id` with a new question instead of a fresh run).
- **Semantic RAG over local PDFs.** A `VectorRagAdapter` (ChromaDB/FAISS) behind the
  existing `EvidenceRetrievalPort` — no domain changes needed.
- **Higher medical rigor.** Evidence pyramid (meta-analysis > RCT > observational)
  and PICO extraction.
- **Containerize the whole stack.** Bring backend (FastAPI) and frontend into the
  compose stack alongside Ollama.
- **Frontend component/e2e tests.** Current coverage is the pure reducer + theme
  logic only.
