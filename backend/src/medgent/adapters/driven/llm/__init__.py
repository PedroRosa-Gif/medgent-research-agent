"""LLM driven adapters — concrete providers behind :class:`LLMPort`.

Houses the provider implementations the agent drives: a real Ollama adapter plus
explicit Groq and Gemini stubs, and the :func:`build_llm` factory that selects
one from settings.

Dependency rule: these adapters implement the ``LLMPort`` defined in
``application.ports`` and may import concrete SDKs (langchain). The core never
imports from here.
"""
