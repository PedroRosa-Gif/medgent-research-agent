"""Graph — LangGraph orchestration of the self-correcting research loop.

Houses the typed agent state and the state-machine wiring
(``planner -> fetch_evidence -> evaluator -> refine/synthesize``) that drives
the bounded self-correction loop.

Dependency rule: the graph depends on ``domain`` and on ports (abstractions).
It must never import concrete ``adapters``; implementations are injected in.
"""
