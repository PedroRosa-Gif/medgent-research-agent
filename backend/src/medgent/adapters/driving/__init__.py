"""Driving adapters — inbound entry points.

Concrete delivery mechanisms that drive the application layer, such as the
FastAPI (Server-Sent Events) web API and a CLI.

Dependency rule: driving adapters depend inward on ``application`` use cases
and on ``domain``. The core never imports from here.
"""
