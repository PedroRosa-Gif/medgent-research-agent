"""Adapters layer — concrete implementations at the edges.

Contains the outermost ring of the hexagon, split into:

- ``driving``: entry points that drive the application (FastAPI, CLI).
- ``driven``: outbound integrations the application drives through ports
  (PubMed/Entrez, web search, LLM providers, the graph checkpointer).

Dependency rule: adapters depend inward on ``application`` (ports/use cases)
and ``domain``. Nothing in the core imports this layer; wiring happens here.
"""
