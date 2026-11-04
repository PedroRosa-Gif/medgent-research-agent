"""Use cases — application-specific business workflows.

Each use case orchestrates domain logic and ports to carry out a single piece
of application behavior (e.g. run a research session).

Dependency rule: use cases depend on ``domain`` and on ports (abstractions)
only. They must never import concrete ``adapters``.
"""
