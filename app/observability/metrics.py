
"""Prometheus metrics for the document-grounded RAG service."""

from prometheus_client import Counter, Histogram


HTTP_REQUESTS = Counter(
    "rag_http_requests_total",
    "Total HTTP requests processed by the API.",
    ["method", "route", "status_code"],
)

HTTP_DURATION = Histogram(
    "rag_http_request_duration_seconds",
    "HTTP request duration, including streamed responses.",
    ["method", "route"],
)

RETRIEVAL_DURATION = Histogram(
    "rag_retrieval_duration_seconds",
    "Time spent retrieving relevant document chunks.",
)

INFERENCE_DURATION = Histogram(
    "rag_inference_duration_seconds",
    "Time spent generating a model response.",
)

TIME_TO_FIRST_TOKEN = Histogram(
    "rag_time_to_first_token_seconds",
    "Time until the first inference output chunk.",
)

INFERENCE_OUTCOMES = Counter(
    "rag_inference_outcomes_total",
    "Inference outcomes by status.",
    ["status"],
)

EVIDENCE_OUTCOMES = Counter(
    "rag_evidence_outcomes_total",
    "Document evidence sufficiency outcomes.",
    ["status"],
)
