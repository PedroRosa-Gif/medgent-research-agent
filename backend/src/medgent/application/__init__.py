"""Application layer — use cases, orchestration, and ports.

Coordinates the domain to fulfill the agent's workflows: it hosts the use
cases, the LangGraph orchestration (the self-correcting research loop), and the
ports (abstract interfaces) that the outside world must implement.

Dependency rule: this layer may import from ``domain`` and defines ports as
abstractions. It must NOT import from ``adapters`` — concrete adapters are wired
in from the outside and depend on these ports, never the other way around.
"""
