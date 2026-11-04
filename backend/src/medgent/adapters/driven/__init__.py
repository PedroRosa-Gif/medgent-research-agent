"""Driven adapters — outbound integrations.

Concrete implementations of application ports for the systems the agent drives:
PubMed/NCBI Entrez and web search retrieval, LLM providers (Ollama/Groq/Gemini),
and the LangGraph checkpointer.

Dependency rule: driven adapters implement ports defined in ``application`` and
may use ``domain`` types. The core never imports from here.
"""
