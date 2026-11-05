"""Graph — LangGraph orchestration of the self-correcting research loop.

Houses the typed agent state and the state-machine wiring
(``planner -> fetch_evidence -> evaluator -> refine/synthesize``) that drives
the bounded self-correction loop.

Dependency rule: the graph depends on ``domain`` and on ports (abstractions).
It must never import concrete ``adapters``; implementations are injected in.
"""

from medgent.application.graph.build import build_graph, route_after_evaluator
from medgent.application.graph.nodes import (
    make_evaluator_node,
    make_fetch_evidence_node,
    make_planner_node,
    make_refine_queries_node,
)

__all__ = [
    "build_graph",
    "make_evaluator_node",
    "make_fetch_evidence_node",
    "make_planner_node",
    "make_refine_queries_node",
    "route_after_evaluator",
]
