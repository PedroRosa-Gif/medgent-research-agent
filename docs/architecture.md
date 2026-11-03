# Medical Deep Research Agent - System Architecture

An autonomous, multi-step agent designed to conduct systematic literature reviews and evidence extraction from medical databases (e.g., PubMed) using local LLMs and LangGraph orchestration.

## High-Level Overview

Unlike traditional single-pass RAG applications, this system implements a self-correcting research loop based on the **ReAct pattern** and **graph-based state machines**. It formulates research strategies, queries public medical repositories, evaluates clinical study quality, and iteratively refines queries until evidence criteria are met.

                  +-----------------------------+
                  |     User Input / Topic      |
                  +--------------+--------------+
                                 |
                                 v
                  +-----------------------------+
                  |        Planner Node         |
                  +--------------+--------------+
                                 |
                                 v
                  +-----------------------------+
                  |     Fetch Papers Node       | <------+
                  |    (PubMed API / Local)     |        |
                  +--------------+--------------+        |
                                 |                       |
                                 v                       | Re-query
                  +-----------------------------+        | (If low quality/
                  |       Evaluator Node        |        |  insufficient data)
                  |  (Checks evidence/sample N) |        |
                  +--------------+--------------+        |
                                 |                       |
                     [Is Evidence Sufficient?]           |
                             /       \                   |
                       Yes  /         \ No (Iter < max)  |
                           /           +-----------------+
                          v
                  +-----------------------------+
                  |      Synthesizer Node       |
                  +--------------+--------------+
                                 |
                                 v
                  +-----------------------------+
                  |   Final Medical Report (.md)|
                  +-----------------------------+

## Component Breakdown

### 1. State Management (`StateGraph`)
The state passes deterministically between nodes as a typed dictionary:

- `topic` (`str`): Original research topic provided by the user.
- `queries` (`List[str]`): Dynamically generated search strings optimized for PubMed/MeSH.
- `papers` (`List[Dict]`): Raw metadata, abstracts, and identifiers retrieved from databases.
- `evaluated_studies` (`List[Dict]`): Filtered papers containing extracted sample sizes, study types, and key findings.
- `iteration` (`int`): Counter to prevent infinite loops (max iterations: 3).
- `is_sufficient` (`bool`): Flag updated by the evaluator node to trigger synthesis.
- `final_report` (`str`): Structured markdown output containing citations.

### 2. Tools
- **`PubMedSearchTool`**: Custom Python tool wrapping the NCBI Entrez API (via `BioPython` or `requests`) to query `pmid`s and fetch structured abstracts.
- **`LocalRAGTool`**: Hybrid semantic/keyword search module to query pre-downloaded clinical trial PDFs.

### 3. Nodes and Logic

| Node Name | Input | Primary Responsibility | Output State Changes |
| :--- | :--- | :--- | :--- |
| `planner` | `topic` | Decomposes the research topic into targeted clinical sub-queries (Mechanism of Action, Efficacy, Adverse Effects). | `queries` |
| `fetch_papers` | `queries` | Executes search tools against PubMed/arXiv or local vector storage. | `papers` |
| `evaluator` | `papers` | Evaluates study methodology, sample size ($N$), and clinical relevance. Determines if criteria are met or if query expansion is needed. | `evaluated_studies`, `is_sufficient`, `iteration` |
| `synthesizer` | `evaluated_studies` | Compiles validated findings into a systematic review with inline citations. | `final_report` |

---

## Tech Stack

- **Orchestration**: LangGraph
- **Local LLM Engine**: Ollama (`qwen2.5:7b` / `llama3.2:3b`)
- **APIs & Data Fetching**: BioPython, NCBI Entrez API, DuckDuckGo Search API
- **Data Model & Validation**: Pydantic v2 / TypedDict
- **Storage / Vector Database**: ChromaDB / FAISS (for local PDF fallback)
- **UI & Logging**: Streamlit (Interface) + Console Execution Traces

---

## Self-Correction Loop (Conditional Routing)

The routing logic after the `evaluator` node is defined as:

1. **`is_sufficient == True`** OR **`iteration >= 3`** $\rightarrow$ Transition to `synthesizer`.
2. **`is_sufficient == False`** AND **`iteration < 3`** $\rightarrow$ Reformulate queries and transition back to `fetch_papers`.