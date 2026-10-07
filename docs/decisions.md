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

---

## ADR-004 — Use a local OpenAI-compatible inference boundary

**Date:** 2026-10-07

### Context

The service must use a local quantized model, remain provider-configurable, and
support genuine progressive streaming without cloud inference.

### Decision

Use Docker Model Runner through its OpenAI-compatible chat-completions API.

Keep the inference endpoint and model identifier environment-driven through
`LLM_URL` and `LLM_MODEL`.

Use an asynchronous `httpx` client that parses streaming SSE events
incrementally.

The final assessment model is:

`huggingface.co/qwen/qwen2.5-0.5b-instruct-gguf:Q4_K_M`

Docker Model Runner reports approximately 630M parameters and Q4_K_M
quantization.

### Rationale

The HTTP boundary keeps retrieval and prompt assembly independent from the
model provider and makes streaming behaviour easy to inspect during review.

Qwen2.5 0.5B was selected because it remains below the assessment's one-billion
parameter limit while producing more reliable grounded answers than the
smaller model tested during development.

### Consequences

Alternative local models can be selected without application-code changes if
they expose the same OpenAI-compatible contract.

Model availability and quality remain operational concerns and must be tested.

---

## ADR-005 — Treat retrieved documents as untrusted evidence

**Date:** 2026-10-07

### Context

Retrieved documents may contain instruction-like or malicious text, while the
application must preserve its own instructions and source attribution.

### Decision

Keep trusted application instructions in the system-message channel.

Place retrieved documents only inside explicitly labelled untrusted evidence
sections.

Source identifiers remain application-controlled rather than model-generated.

Chat responses are exposed as server-sent events with separate `sources`,
`token`, `done`, and `error` event types.

### Rationale

This creates a clear trust boundary between application policy and document
content.

Structured SSE events allow the client to distinguish answer text, source
metadata, normal completion, and inference failure.

### Consequences

Prompt-injection resistance must still be tested with adversarial documents.

Clients must handle partial streams and structured error events correctly.
