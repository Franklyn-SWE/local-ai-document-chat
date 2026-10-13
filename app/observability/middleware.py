
"""Request correlation, HTTP lifecycle logging and Prometheus metrics."""

import logging
import time
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.observability.metrics import HTTP_REQUESTS, HTTP_DURATION

logger = logging.getLogger("app.observability.http")


class RequestLoggingMiddleware:
    """Track HTTP requests, including streamed response completion."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        start = time.perf_counter()
        status_code = 500
        completed = False

        method = scope.get("method", "")
        path = scope.get("path", "")

        # Prevent arbitrary paths from creating high-cardinality labels.
        safe_path = (
            path
            if path in ("/chat", "/health", "/metrics")
            else "/other"
        )

        logger.info(
            "http.request.started",
            extra={"request_id": request_id},
        )

        async def send_with_logging(message: Message) -> None:
            nonlocal status_code, completed

            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", []).append(
                    (b"x-request-id", request_id.encode("ascii"))
                )

            await send(message)

            if (
                message["type"] == "http.response.body"
                and not message.get("more_body", False)
            ):
                completed = True
                duration_seconds = time.perf_counter() - start

                # Prometheus: request count and end-to-end latency.
                HTTP_REQUESTS.labels(
                    method=method,
                    route=safe_path,
                    status_code=str(status_code),
                ).inc()

                HTTP_DURATION.labels(
                    method=method,
                    route=safe_path,
                ).observe(duration_seconds)

                # Structured JSON logging.
                logger.info(
                    "http.request.completed",
                    extra={
                        "request_id": request_id,
                        "status_code": status_code,
                        "duration_ms": round(
                            duration_seconds * 1000, 2
                        ),
                    },
                )

        try:
            await self.app(scope, receive, send_with_logging)

        except Exception as exc:
            logger.error(
                "http.request.failed",
                extra={
                    "request_id": request_id,
                    "error_type": type(exc).__name__,
                    "status_code": status_code,
                },
            )
            raise
