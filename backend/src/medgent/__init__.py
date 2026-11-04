"""MedGent Research Agent — backend package.

Top-level package for the hexagonal (ports & adapters) backend. The package is
organized into three layers whose dependency direction flows inward:

    adapters  ->  application  ->  domain

- ``domain``: pure business logic, zero framework imports.
- ``application``: use cases, LangGraph orchestration, and ports (interfaces).
- ``adapters``: concrete driving/driven implementations of those ports.

The domain never imports the application or adapters; the application never
imports adapters. Only adapters depend on the core.
"""

__version__ = "0.1.0"
