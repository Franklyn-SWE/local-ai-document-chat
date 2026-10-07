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

---

## ADR-002 — Use polling and immutable corpus snapshots for live refresh

**Date:** 2026-10-07

### Context

Documents may be added, modified, renamed, or removed while the service is
running. Subsequent requests must use only the current corpus, and files may
be observed while they are still being written.

### Decision

Use periodic filesystem polling with a configurable stability delay.

When a stable change is detected, build a complete new immutable corpus
snapshot and atomically replace the active snapshot.

### Alternatives considered

- Native filesystem event watchers
- Manual re-index endpoint
- Mutating the active corpus in place

### Rationale

Polling provides predictable behaviour across local development and Docker
bind mounts.

Immutable snapshot replacement prevents requests from observing partially
updated corpus state and ensures removed documents cannot leave stale chunks
behind.

### Consequences

Corpus updates are eventually consistent rather than instantaneous.

A filesystem change is considered ready to serve after it has been detected,
its signature has remained unchanged for the configured stability period, and
the complete replacement snapshot has been successfully built and promoted.
