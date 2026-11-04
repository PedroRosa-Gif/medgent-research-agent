# MedGent Research Agent

> Autonomous deep-research agent for clinical literature — it plans a research
> strategy, gathers evidence from medical databases and the web, critiques study
> quality in a self-correcting loop, and synthesizes a cited report.

![status](https://img.shields.io/badge/status-planning%20%2F%20in%20active%20development-orange)
![license](https://img.shields.io/badge/license-TBD-lightgrey)

> 🚧 **Project status**: early stage. Architecture is designed; implementation is
> starting. The README will grow a real quickstart, screenshots, and a live demo as
> the code lands.

> ⚠️ **Disclaimer**: This is a study/research tool. It does **not** provide medical
> advice, diagnosis, or treatment.

---

## What it is

Most "chat with documents" demos do a single retrieval pass and call it a day.
MedGent is built around a **self-correcting research loop**: it decomposes a topic
into clinical sub-questions, retrieves evidence, *evaluates the quality of what it
found*, and decides on its own whether to dig deeper or write the report — all as a
**graph-based state machine** you can watch reason in real time.

It is a personal portfolio project with two explicit goals:

1. **Go deep** on LangGraph, agent state management, retrieval-augmented generation
   (structured *and* semantic), and clean architecture.
2. **Show engineering maturity** — typed state, a self-correcting agent loop,
   provider abstraction, a hexagonal core, and a real-time reasoning UI.

## Why it's interesting (the technical gist)

- **Self-correcting loop, not single-pass RAG** — a `planner → fetch → evaluate →
  refine/synthesize` graph that re-queries when the evidence is weak, bounded by an
  iteration ceiling.
- **Hybrid evaluator** — deterministic heuristics (study type, sample size,
  recency) *plus* structured LLM extraction (Pydantic), because small models should
  not be trusted to judge everything alone.
- **Hexagonal architecture (ports & adapters)** — a framework-free domain; LangGraph
  lives in the application layer and depends on ports, so PubMed, the LLM, and the
  web delivery are swappable adapters.
- **Structured *and* semantic RAG** — structured retrieval (NCBI Entrez / web) today,
  with embedding-based PDF search reserved behind the same port for later.
- **Provider-abstracted LLMs, free by default** — local **Ollama** out of the box,
  with optional **Groq** / **Gemini** free tiers for higher-quality synthesis.
- **Reasoning you can see** — a React single-page app streams each step of the
  agent's thinking over SSE.

## Architecture

The agent is a LangGraph state machine with a bounded self-correction loop:

```mermaid
flowchart TD
    Start([User Topic]) --> Planner[planner]
    Planner --> Fetch[fetch_evidence<br/>PubMed + Web]
    Fetch --> Evaluator[evaluator<br/>heuristics + structured LLM]
    Evaluator --> Decision{sufficient?<br/>or max iterations?}
    Decision -- No --> Refine[refine_queries] --> Fetch
    Decision -- Yes --> Synth[synthesizer] --> End([Cited Report])
```

📄 Full design, component breakdown, and design-decision rationale:
[`docs/architecture.md`](docs/architecture.md).

## Tech stack

| Area | Choice |
| :--- | :--- |
| Agent orchestration | LangGraph (compiled with a checkpointer) |
| LLM (abstracted) | Ollama (default) · Groq · Google Gemini |
| Structured retrieval | NCBI Entrez (PubMed) · DuckDuckGo Search |
| Semantic retrieval (future) | ChromaDB / FAISS |
| Validation / config | Pydantic v2 · pydantic-settings |
| API | FastAPI + Server-Sent Events |
| Front end | React · Vite · TypeScript · Tailwind (dark mode) |
| Observability | native step trace · optional LangSmith |
| Testing / tooling | pytest · ruff |

## Repository layout (planned monorepo)

```
medgent-research-agent/
├── backend/        # Python — hexagonal core + LangGraph + FastAPI/CLI adapters
├── frontend/       # React + Vite single-page reasoning UI
├── docs/           # architecture and design notes
└── README.md
```

## Roadmap

- [x] System architecture & design
- [x] Project scaffolding (hexagonal layout, tooling, CI)
- [ ] Agent state & Pydantic schemas
- [ ] LLM provider abstraction (Ollama / Groq / Gemini)
- [ ] Retrieval adapters (PubMed, web search)
- [ ] Graph nodes + self-correction loop + checkpointer
- [ ] FastAPI streaming (SSE) API
- [ ] React single-page reasoning UI
- [ ] Optional LangSmith observability, polish & demo

### Future extensions

- Conversational follow-up mode (enabled by the checkpointer foundation)
- Semantic RAG over local clinical PDFs (new adapter, same port)
- Higher medical rigor: evidence pyramid and PICO extraction
