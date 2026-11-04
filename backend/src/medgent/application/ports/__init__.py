"""Ports — abstract interfaces the outside world must satisfy.

Defines the boundaries (abstract base classes / protocols) for driven
dependencies such as the LLM provider, literature/web retrieval, and the graph
checkpointer, as well as any driving contracts.

Dependency rule: ports depend only on ``domain`` types. Concrete adapters
implement these interfaces; ports never import adapters.
"""
