# Decision Log

This document records significant engineering decisions in the order they are made.

---

## ADR-001 — Keep the architecture deliberately small

**Date:** 2026-10-07

### Context

The assessment prioritises local operation, explainability, security,
observability, reproducibility, and code ownership.

### Decision

Use a small modular Python application with:

- FastAPI for the backend API
- Streamlit for the browser interface
- Docker Model Runner for local inference
- a lightweight local retrieval approach
- local structured logging and tracing

### Rationale

A deliberately small architecture reduces unnecessary dependencies and makes
the request path, failure modes, security boundaries, and operational behaviour
easier to test and explain during a live review.

### Alternatives considered

More complex RAG frameworks, external vector databases, and hosted AI services.

### Consequences

Some advanced retrieval features are intentionally deferred unless they are
shown to be necessary.
