

"""
Purpose:
    Exposes the document-grounded chat endpoint and streams model output
    progressively to the client.

Place in the system:
    This is the request orchestration layer. It connects the active corpus,
    retrieval, guarded prompt assembly, and local inference client.

Observability:
    Records retrieval latency, evidence sufficiency, inference duration,
    time to first token, output chunk count, and inference outcome.

    Exposes Prometheus metrics alongside structured JSON logs.
    Uses request IDs to correlate events without logging sensitive content.
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.corpus.state import CorpusState
from app.inference.client import LocalInferenceClient
from app.inference.models import InferenceError, InferenceRequest
from app.observability.metrics import (
    RETRIEVAL_DURATION,
    INFERENCE_DURATION,
    TIME_TO_FIRST_TOKEN,
    INFERENCE_OUTCOMES,
    EVIDENCE_OUTCOMES,
)
from app.prompting.builder import build_prompt
from app.retrieval.bm25 import retrieve


router = APIRouter()
logger = logging.getLogger("app.api.chat")


class ChatRequest(BaseModel):
    """Validated incoming chat request."""

    question: str = Field(min_length=1, max_length=4000)


def _event(event_type: str, payload: dict[str, object]) -> str:
    """Encode one server-sent event."""
    return (
        f"event: {event_type}\n"
        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    )


def create_chat_router(corpus_state: CorpusState) -> APIRouter:
    """Create a chat router bound to the active corpus state."""

    @router.post("/chat")
    async def chat(
        request: ChatRequest,
        http_request: Request,
    ) -> StreamingResponse:
        settings = get_settings()
        request_id = http_request.state.request_id

        question = request.question.strip()

        if not question:
            raise HTTPException(
                status_code=400,
                detail="question must not be empty",
            )

        snapshot = corpus_state.get_snapshot()

        # --------------------------------------------------
        # 1. BM25 retrieval observability
        # --------------------------------------------------

        retrieval_start = time.perf_counter()

        result = retrieve(
            question,
            snapshot.chunks,
            top_k=settings.retrieval_top_k,
            min_score=settings.retrieval_min_score,
            token_budget=settings.context_token_budget,
        )

        retrieval_seconds = time.perf_counter() - retrieval_start
        retrieval_ms = round(retrieval_seconds * 1000, 2)

        # Prometheus: retrieval latency.
        RETRIEVAL_DURATION.observe(retrieval_seconds)

        # Prometheus: evidence sufficiency.
        EVIDENCE_OUTCOMES.labels(
            status=(
                "insufficient"
                if result.insufficient_evidence
                else "sufficient"
            )
        ).inc()

        # Structured logging.
        logger.info(
            "rag.retrieval.completed",
            extra={
                "request_id": request_id,
                "retrieval_ms": retrieval_ms,
                "selected_chunks": len(result.selected),
                "insufficient_evidence": result.insufficient_evidence,
            },
        )

        # --------------------------------------------------
        # 2. Insufficient evidence handling
        # --------------------------------------------------

        if result.insufficient_evidence:

            async def insufficient_stream() -> AsyncIterator[str]:
                yield _event(
                    "status",
                    {
                        "status": "insufficient_evidence",
                        "message": (
                            "The available documents do not contain enough "
                            "relevant evidence to answer this question."
                        ),
                    },
                )

            return StreamingResponse(
                insufficient_stream(),
                media_type="text/event-stream",
            )

        # --------------------------------------------------
        # 3. Grounded prompt construction
        # --------------------------------------------------

        prompt = build_prompt(
            question,
            result.selected,
        )

        client = LocalInferenceClient(
            base_url=str(settings.llm_url),
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )

        # --------------------------------------------------
        # 4. Streaming inference observability
        # --------------------------------------------------

        async def stream_response() -> AsyncIterator[str]:
            yield _event(
                "sources",
                {
                    "source_ids": list(prompt.source_ids),
                    "estimated_context_tokens": (
                        result.estimated_context_tokens
                    ),
                    "token_budget": result.token_budget,
                    "excluded_by_budget": result.excluded_by_budget,
                },
            )

            inference_start = time.perf_counter()

            ttft_ms = None
            output_chunks = 0
            inference_status = "interrupted"

            try:
                async for text in client.stream(
                    InferenceRequest(
                        system_prompt=prompt.system_prompt,
                        user_prompt=prompt.user_prompt,
                    )
                ):
                    # Time to first generated text.
                    if ttft_ms is None:
                        ttft_seconds = (
                            time.perf_counter() - inference_start
                        )

                        ttft_ms = round(ttft_seconds * 1000, 2)

                        # Prometheus: record TTFT once.
                        TIME_TO_FIRST_TOKEN.observe(ttft_seconds)

                    output_chunks += 1

                    yield _event(
                        "token",
                        {"text": text},
                    )

                inference_status = "completed"

                yield _event(
                    "done",
                    {"status": "complete"},
                )

            except InferenceError as exc:
                inference_status = "failed"

                yield _event(
                    "error",
                    {
                        "status": "inference_failed",
                        "message": str(exc),
                    },
                )

            except asyncio.CancelledError:
                inference_status = "cancelled"
                raise

            finally:
                inference_seconds = (
                    time.perf_counter() - inference_start
                )

                inference_ms = round(
                    inference_seconds * 1000,
                    2,
                )

                # Prometheus: total inference duration.
                INFERENCE_DURATION.observe(inference_seconds)

                # Prometheus: inference outcome.
                INFERENCE_OUTCOMES.labels(
                    status=inference_status
                ).inc()

                # Structured JSON logging.
                logger.info(
                    "rag.inference.completed",
                    extra={
                        "request_id": request_id,
                        "inference_ms": inference_ms,
                        "ttft_ms": ttft_ms,
                        "output_chunks": output_chunks,
                        "inference_status": inference_status,
                    },
                )

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
        )

    return router
