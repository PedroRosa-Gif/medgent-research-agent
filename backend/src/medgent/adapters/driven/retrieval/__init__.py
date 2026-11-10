"""Retrieval driven adapters — concrete sources behind :class:`EvidenceRetrievalPort`.

Houses the evidence sources the agent drives. The MVP ships a PubMed adapter that
runs a structured search against NCBI E-utilities; web and semantic-search
adapters slot in here later behind the same port.

Dependency rule: these adapters implement the ``EvidenceRetrievalPort`` defined in
``application.ports`` and may import concrete I/O libraries (``requests``, stdlib
XML parsing). The core never imports from here.
"""
