"""HTTP (FastAPI) driving adapter — the web entry point for research runs.

A second *driving* adapter alongside the CLI, and a composition root: it reads
:func:`get_settings`, builds the concrete adapters (via
:func:`medgent.adapters.driving.composition.build_use_case`), and wires them into
the *same* :class:`ResearchTopicUseCase` the CLI uses — one core, two delivery
mechanisms. It exposes a synchronous ``POST /research`` plus a Server-Sent Events
``GET /research/stream`` endpoint that relays the agent's reasoning in real time.

Dependency rule: this package may import FastAPI, the use case, config, and the
concrete adapters (it is the composition root). It contains no business logic —
only translation between HTTP and the use case.
"""
