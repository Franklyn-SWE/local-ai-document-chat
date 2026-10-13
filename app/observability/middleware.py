
"""Request correlation and HTTP lifecycle logging."""

import logging
import time
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app.observability.http")


class RequestLoggingMiddleware:
    """Log requests, including completion of streamed responses."""

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

        # Avoid logging arbitrary user-controlled paths.
        safe_path = path if path in ("/chat", "/health") else "/other"

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
                logger.info(
                    "http.request.completed",
                    extra={
                        "request_id": request_id,
                        "status_code": status_code,
                        "duration_ms": round(
                            (time.perf_counter() - start) * 1000, 2
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
