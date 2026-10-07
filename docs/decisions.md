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

---

## ADR-003 — Use lexical retrieval with explicit context budgeting

**Date:** 2026-10-07

### Context

The service needs to select evidence from a small local corpus while remaining
fully local, explainable, and easy to review.

### Decision

Use a small BM25-style lexical retriever over the current immutable corpus
snapshot.

Rank candidate chunks, apply a configurable top-k and minimum relevance score,
then select only chunks that fit within an explicit context-token budget.

Token counts are currently estimated using approximately four characters per
token and are labelled as estimates.

### Alternatives considered

- Embedding-based semantic retrieval
- Vector databases such as Qdrant
- RAG frameworks with built-in retrievers

### Rationale

Lexical retrieval removes the need for an embedding model and vector database,
keeps the system offline and deterministic, and makes evidence selection easy
to inspect during live review.

### Consequences

Semantic matching is weaker when user terminology differs significantly from
the source documents. This is an accepted limitation for the assessment-scale
corpus.
