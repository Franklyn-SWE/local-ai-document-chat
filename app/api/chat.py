"""
Purpose:
    Exposes the document-grounded chat endpoint and streams model output
    progressively to the client.

Place in the system:
    This is the request orchestration layer. It connects the active corpus,
    retrieval, guarded prompt assembly, and local inference client.
"""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.corpus.state import CorpusState
from app.inference.client import LocalInferenceClient
from app.inference.models import InferenceError, InferenceRequest
from app.prompting.builder import build_prompt
from app.retrieval.bm25 import retrieve

router = APIRouter()


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
    """Create a chat router bound to the application's active corpus state."""

    @router.post("/chat")
    async def chat(request: ChatRequest) -> StreamingResponse:
        settings = get_settings()

        question = request.question.strip()

        if not question:
            raise HTTPException(
                status_code=400,
                detail="question must not be empty",
            )

        snapshot = corpus_state.get_snapshot()

        result = retrieve(
            question,
            snapshot.chunks,
            top_k=settings.retrieval_top_k,
            min_score=settings.retrieval_min_score,
            token_budget=settings.context_token_budget,
        )

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

        prompt = build_prompt(
            question,
            result.selected,
        )

        client = LocalInferenceClient(
            base_url=str(settings.llm_url),
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )

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

            try:
                async for text in client.stream(
                    InferenceRequest(
                        system_prompt=prompt.system_prompt,
                        user_prompt=prompt.user_prompt,
                    )
                ):
                    yield _event(
                        "token",
                        {"text": text},
                    )

                yield _event(
                    "done",
                    {"status": "complete"},
                )

            except InferenceError as exc:
                yield _event(
                    "error",
                    {
                        "status": "inference_failed",
                        "message": str(exc),
                    },
                )

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
        )

    return router