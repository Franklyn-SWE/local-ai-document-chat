"""
Purpose:
    Creates the FastAPI application and wires together shared runtime services.

Place in the system:
    This is the backend application composition root. It owns the shared corpus
    state, starts the live corpus watcher, and registers HTTP routes including
    health and document-grounded chat.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.chat import create_chat_router
from app.api.health import router as health_router
from app.config import get_settings
from app.corpus.state import CorpusState, build_snapshot
from app.corpus.watcher import CorpusWatcher

settings = get_settings()

# Build the first complete corpus snapshot before serving requests.
initial_snapshot = build_snapshot(
    Path(settings.data_dir),
    chunk_size=settings.chunk_size_chars,
    overlap=settings.chunk_overlap_chars,
)

# One shared state object is read by chat requests and updated by the watcher.
corpus_state = CorpusState(initial_snapshot)

corpus_watcher = CorpusWatcher(
    data_dir=Path(settings.data_dir),
    state=corpus_state,
    chunk_size=settings.chunk_size_chars,
    overlap=settings.chunk_overlap_chars,
    poll_interval_seconds=settings.corpus_poll_interval_seconds,
    stability_delay_seconds=settings.corpus_stability_delay_seconds,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Start the corpus watcher with the application and stop it cleanly.

    The watcher promotes stable filesystem changes into the shared CorpusState,
    so later requests see the current corpus without a restart.
    """
    watcher_task = asyncio.create_task(corpus_watcher.run())

    try:
        yield
    finally:
        watcher_task.cancel()

        try:
            await watcher_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Local RAG Document Chat",
    version="0.1.0",
    description="Local document-grounded chat service.",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(create_chat_router(corpus_state))