
"""Tests for structured logging and HTTP request observability."""

import json
import logging
import re

import pytest

from app.observability.logging import JSONFormatter
from app.observability.middleware import RequestLoggingMiddleware


def make_log_record(event: str) -> logging.LogRecord:
    """Create a log record for testing structured JSON output."""
    return logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=event,
        args=(),
        exc_info=None,
    )


def test_json_formatter_includes_observability_fields():
    """Operational fields should be present in JSON logs."""
    formatter = JSONFormatter()

    record = make_log_record("rag.retrieval.completed")
    record.request_id = "test-request-001"
    record.retrieval_ms = 12.5
    record.selected_chunks = 2
    record.insufficient_evidence = False

    data = json.loads(formatter.format(record))

    assert data["level"] == "INFO"
    assert data["event"] == "rag.retrieval.completed"
    assert data["request_id"] == "test-request-001"
    assert data["retrieval_ms"] == 12.5
    assert data["selected_chunks"] == 2
    assert data["insufficient_evidence"] is False
    assert "timestamp" in data


def test_json_formatter_excludes_sensitive_extra_fields():
    """Unapproved fields must not appear in logs."""
    formatter = JSONFormatter()

    record = make_log_record("rag.inference.completed")
    record.request_id = "test-request-002"
    record.user_question = "Private user question"
    record.document_content = "Confidential document text"
    record.model_answer = "Sensitive generated answer"

    data = json.loads(formatter.format(record))

    assert "user_question" not in data
    assert "document_content" not in data
    assert "model_answer" not in data


def test_json_formatter_includes_inference_metrics():
    """Inference performance fields should be retained."""
    formatter = JSONFormatter()

    record = make_log_record("rag.inference.completed")
    record.request_id = "test-request-003"
    record.inference_ms = 1500.0
    record.ttft_ms = 350.0
    record.output_chunks = 12
    record.inference_status = "completed"

    data = json.loads(formatter.format(record))

    assert data["inference_ms"] == 1500.0
    assert data["ttft_ms"] == 350.0
    assert data["output_chunks"] == 12
    assert data["inference_status"] == "completed"


@pytest.mark.asyncio
async def test_middleware_generates_request_id():
    """Every HTTP response should include a generated request ID."""
    messages = []

    async def fake_app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"status":"ok"}',
            "more_body": False,
        })

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        messages.append(message)

    middleware = RequestLoggingMiddleware(fake_app)

    await middleware(
        {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [],
        },
        receive,
        send,
    )

    response_start = next(
        message
        for message in messages
        if message["type"] == "http.response.start"
    )

    headers = dict(response_start["headers"])
    request_id = headers[b"x-request-id"].decode("ascii")

    assert re.fullmatch(r"[0-9a-f]{32}", request_id)


@pytest.mark.asyncio
async def test_middleware_logs_stream_completion(caplog):
    """Completion must be logged once after the final streamed body."""
    messages = []

    async def fake_app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [],
        })

        await send({
            "type": "http.response.body",
            "body": b"first",
            "more_body": True,
        })

        await send({
            "type": "http.response.body",
            "body": b"second",
            "more_body": False,
        })

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        messages.append(message)

    middleware = RequestLoggingMiddleware(fake_app)
    app_logger = logging.getLogger("app.observability.http")

    # Capture logs directly without duplicate propagation.
    original_propagate = app_logger.propagate
    app_logger.propagate = False
    app_logger.addHandler(caplog.handler)

    try:
        with caplog.at_level(
            logging.INFO,
            logger="app.observability.http",
        ):
            await middleware(
                {
                    "type": "http",
                    "method": "GET",
                    "path": "/health",
                    "headers": [],
                },
                receive,
                send,
            )
    finally:
        app_logger.removeHandler(caplog.handler)
        app_logger.propagate = original_propagate

    completed = [
        record
        for record in caplog.records
        if record.getMessage() == "http.request.completed"
    ]

    assert len(completed) == 1
    assert completed[0].status_code == 200
    assert completed[0].duration_ms >= 0

    body_messages = [
        message
        for message in messages
        if message["type"] == "http.response.body"
    ]

    assert len(body_messages) == 2
    assert body_messages[-1]["body"] == b"second"
    assert body_messages[-1].get("more_body", False) is False
