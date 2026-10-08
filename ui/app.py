"""
Purpose:
    Provides the browser interface for asking questions and displaying
    progressively streamed document-grounded answers.

Place in the system:
    This is the presentation layer. It communicates with the FastAPI backend
    and does not perform corpus loading, retrieval, prompting, or inference.
"""

import json
from collections.abc import Iterator
from typing import Any

import httpx
import streamlit as st
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class UISettings(BaseSettings):
    """Validated configuration used by the Streamlit presentation layer."""

    backend_url: str = Field(
        default="http://127.0.0.1:8000",
        min_length=1,
        alias="BACKEND_URL",
    )

    request_timeout_seconds: float = Field(
        default=90.0,
        gt=0,
        alias="UI_REQUEST_TIMEOUT_SECONDS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = UISettings()
backend_url = settings.backend_url.rstrip("/")


def _backend_is_healthy() -> bool:
    """Return whether the local FastAPI backend is reachable."""
    try:
        response = httpx.get(
            f"{backend_url}/health",
            timeout=2.0,
        )
        return response.status_code == 200
    except httpx.RequestError:
        return False


def _iter_sse_events(
    response: httpx.Response,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Parse the small SSE contract exposed by the FastAPI chat endpoint."""
    event_type = "message"

    for line in response.iter_lines():
        if not line:
            event_type = "message"
            continue

        if line.startswith("event:"):
            event_type = line.removeprefix("event:").strip()
            continue

        if not line.startswith("data:"):
            continue

        raw_data = line.removeprefix("data:").strip()

        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError:
            yield (
                "error",
                {
                    "message": (
                        "The backend returned malformed streaming data."
                    )
                },
            )
            return

        if not isinstance(payload, dict):
            yield (
                "error",
                {
                    "message": (
                        "The backend returned an unexpected streaming event."
                    )
                },
            )
            return

        yield event_type, payload


def _render_sources(
    payload: dict[str, Any],
    placeholder: Any,
) -> None:
    """Render application-controlled sources and context-budget information."""
    raw_sources = payload.get("source_ids")

    with placeholder.container():
        st.markdown("#### Sources")

        if isinstance(raw_sources, list):
            valid_sources = [
                source
                for source in raw_sources
                if isinstance(source, str)
            ]

            if valid_sources:
                for source in valid_sources:
                    # Source identifiers are rendered as plain text so they
                    # cannot introduce executable browser content.
                    st.text(source)
            else:
                st.caption("No source identifiers were returned.")

        estimated_tokens = payload.get("estimated_context_tokens")
        token_budget = payload.get("token_budget")
        excluded = payload.get("excluded_by_budget")

        if isinstance(estimated_tokens, int) and isinstance(token_budget, int):
            excluded_count = excluded if isinstance(excluded, int) else 0

            st.caption(
                "Estimated evidence tokens: "
                f"{estimated_tokens} / {token_budget} · "
                f"Excluded by budget: {excluded_count}"
            )


def _stream_answer(question: str) -> None:
    """Send a question and progressively render the backend SSE response."""
    answer_placeholder = st.empty()
    sources_placeholder = st.empty()
    status_placeholder = st.empty()

    answer = ""
    completed = False
    failed = False

    timeout = httpx.Timeout(
        settings.request_timeout_seconds,
        connect=5.0,
    )

    try:
        with httpx.stream(
            "POST",
            f"{backend_url}/chat",
            json={"question": question},
            timeout=timeout,
        ) as response:
            response.raise_for_status()

            for event_type, payload in _iter_sse_events(response):
                if event_type == "sources":
                    _render_sources(
                        payload,
                        sources_placeholder,
                    )
                    continue

                if event_type == "token":
                    text = payload.get("text")

                    if isinstance(text, str):
                        answer += text

                        # Model output is untrusted. Plain-text rendering keeps
                        # HTML and script-like content inert in the browser.
                        answer_placeholder.text(answer)

                    continue

                if event_type == "status":
                    message = payload.get("message")

                    if isinstance(message, str):
                        status_placeholder.info(message)
                    else:
                        status_placeholder.info(
                            "The available evidence is insufficient."
                        )

                    completed = True
                    continue

                if event_type == "error":
                    message = payload.get("message")

                    if isinstance(message, str):
                        status_placeholder.error(message)
                    else:
                        status_placeholder.error(
                            "The local inference request failed."
                        )

                    failed = True
                    continue

                if event_type == "done":
                    completed = True
                    status_placeholder.caption("Response complete.")

    except httpx.ConnectError:
        failed = True
        status_placeholder.error(
            "The local API is unavailable. Check that the backend is running."
        )

    except httpx.TimeoutException:
        failed = True
        status_placeholder.error(
            "The request timed out before the response completed."
        )

    except httpx.HTTPStatusError as exc:
        failed = True
        status_placeholder.error(
            f"The backend rejected the request "
            f"(HTTP {exc.response.status_code})."
        )

    except httpx.RequestError:
        failed = True
        status_placeholder.error(
            "The connection to the local API was interrupted."
        )

    if not completed and not failed:
        status_placeholder.warning(
            "The response stream ended before completion."
        )


st.set_page_config(
    page_title="Local RAG Document Chat",
    page_icon="📚",
    layout="centered",
)

st.title("Local RAG Document Chat")

st.caption(
    "Ask questions grounded only in the documents currently "
    "available in the local corpus."
)

with st.sidebar:
    st.subheader("System status")

    if _backend_is_healthy():
        st.success("Backend online")
    else:
        st.error("Backend unavailable")

    st.caption("Local inference via Docker Model Runner")

with st.form("question_form"):
    question = st.text_area(
        "Question",
        placeholder=(
            "Example: How many days per week can employees work remotely?"
        ),
        height=100,
        max_chars=4000,
    )

    submitted = st.form_submit_button(
        "Ask documents",
        type="primary",
    )

if submitted:
    cleaned_question = question.strip()

    if not cleaned_question:
        st.warning("Enter a question before submitting.")
    else:
        st.markdown("### Answer")
        _stream_answer(cleaned_question)