
"""Tests for Prometheus RAG metrics."""

from prometheus_client import generate_latest

from app.observability.metrics import (
    HTTP_REQUESTS,
    HTTP_DURATION,
    RETRIEVAL_DURATION,
    INFERENCE_DURATION,
    TIME_TO_FIRST_TOKEN,
    INFERENCE_OUTCOMES,
    EVIDENCE_OUTCOMES,
)


def test_prometheus_metrics_are_registered():
    """All expected RAG metrics are exposed."""
    output = generate_latest().decode("utf-8")

    expected_metrics = [
        "rag_http_requests_total",
        "rag_http_request_duration_seconds",
        "rag_retrieval_duration_seconds",
        "rag_inference_duration_seconds",
        "rag_time_to_first_token_seconds",
        "rag_inference_outcomes_total",
        "rag_evidence_outcomes_total",
    ]

    for metric in expected_metrics:
        assert metric in output


def test_retrieval_histogram_records_observation():
    """Retrieval latency observations increase the sample count."""
    before = RETRIEVAL_DURATION.collect()[0].samples
    before_count = next(
        sample.value for sample in before
        if sample.name == "rag_retrieval_duration_seconds_count"
    )

    RETRIEVAL_DURATION.observe(0.025)

    after = RETRIEVAL_DURATION.collect()[0].samples
    after_count = next(
        sample.value for sample in after
        if sample.name == "rag_retrieval_duration_seconds_count"
    )

    assert after_count == before_count + 1


def test_inference_outcome_counter():
    """Completed inference outcomes increment correctly."""
    counter = INFERENCE_OUTCOMES.labels(status="completed")

    before = counter._value.get()
    counter.inc()
    after = counter._value.get()

    assert after == before + 1


def test_evidence_outcome_counter():
    """Evidence sufficiency counters increment correctly."""
    counter = EVIDENCE_OUTCOMES.labels(status="sufficient")

    before = counter._value.get()
    counter.inc()
    after = counter._value.get()

    assert after == before + 1


def test_inference_histograms_record_observations():
    """Inference and TTFT histograms accept duration observations."""
    INFERENCE_DURATION.observe(1.5)
    TIME_TO_FIRST_TOKEN.observe(0.4)

    output = generate_latest().decode("utf-8")

    assert "rag_inference_duration_seconds_count" in output
    assert "rag_time_to_first_token_seconds_count" in output
