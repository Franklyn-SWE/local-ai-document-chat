"""
Purpose:
    Sends guarded prompts to an OpenAI-compatible local inference endpoint.

Place in the system:
    This module is the only component that knows the model HTTP protocol.
    Retrieval and prompt assembly remain provider-independent.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.inference.models import InferenceError, InferenceRequest


class LocalInferenceClient:
    """Small async client for an OpenAI-compatible local model endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds

    async def stream(
        self,
        request: InferenceRequest,
    ) -> AsyncIterator[str]:
        """Yield model text incrementally as SSE events arrive."""
        payload: dict[str, Any] = {
            "model": self._model,
            "stream": True,
            "messages": [
                {
                    "role": "system",
                    "content": request.system_prompt,
                },
                {
                    "role": "user",
                    "content": request.user_prompt,
                },
            ],
        }

        url = f"{self._base_url}/chat/completions"

        try:
            timeout = httpx.Timeout(self._timeout_seconds)

            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue

                        data = line.removeprefix("data:").strip()

                        if not data:
                            continue

                        if data == "[DONE]":
                            break

                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError as exc:
                            raise InferenceError(
                                "local model returned an invalid stream event"
                            ) from exc

                        choices = event.get("choices", [])

                        if not choices:
                            continue

                        delta = choices[0].get("delta", {})
                        content = delta.get("content")

                        if isinstance(content, str) and content:
                            yield content

        except httpx.TimeoutException as exc:
            raise InferenceError(
                "local model request timed out"
            ) from exc

        except httpx.HTTPStatusError as exc:
            raise InferenceError(
                f"local model returned HTTP {exc.response.status_code}"
            ) from exc

        except httpx.RequestError as exc:
            raise InferenceError(
                "local model is unavailable"
            ) from exc