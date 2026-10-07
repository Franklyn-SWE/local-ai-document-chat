"""
Purpose:
    Builds and stores immutable, versioned snapshots of the current document corpus.

Place in the system:
    This module provides the consistency boundary between live corpus ingestion
    and request processing. Requests read one complete snapshot while refreshes
    construct and atomically replace the next snapshot.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from threading import RLock

from app.corpus.chunker import chunk_documents
from app.corpus.loader import load_corpus
from app.corpus.models import CorpusIssue, DocumentChunk, SourceDocument


@dataclass(frozen=True, slots=True)
class CorpusSnapshot:
    """One complete immutable view of the corpus."""

    version: str
    created_at: datetime
    documents: tuple[SourceDocument, ...]
    chunks: tuple[DocumentChunk, ...]
    issues: tuple[CorpusIssue, ...]

    @property
    def file_count(self) -> int:
        """Return the number of valid source documents."""
        return len(self.documents)

    @property
    def chunk_count(self) -> int:
        """Return the number of retrieval-ready chunks."""
        return len(self.chunks)


def _calculate_version(
    documents: tuple[SourceDocument, ...],
) -> str:
    """Create a stable content-derived version identifier."""
    digest = sha256()

    for document in documents:
        digest.update(document.relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(document.content.encode("utf-8"))
        digest.update(b"\0")

    return digest.hexdigest()[:12]


def build_snapshot(
    data_dir: str | Path,
    *,
    chunk_size: int,
    overlap: int,
) -> CorpusSnapshot:
    """Build one complete immutable corpus snapshot."""
    load_result = load_corpus(data_dir)

    chunks = chunk_documents(
        load_result.documents,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    return CorpusSnapshot(
        version=_calculate_version(load_result.documents),
        created_at=datetime.now(UTC),
        documents=load_result.documents,
        chunks=chunks,
        issues=load_result.issues,
    )


class CorpusState:
    """Thread-safe holder for the currently active corpus snapshot."""

    def __init__(self, initial_snapshot: CorpusSnapshot) -> None:
        self._snapshot = initial_snapshot
        self._lock = RLock()

    def get_snapshot(self) -> CorpusSnapshot:
        """Return the currently active immutable snapshot."""
        with self._lock:
            return self._snapshot

    def replace(self, snapshot: CorpusSnapshot) -> None:
        """Atomically replace the active snapshot."""
        with self._lock:
            self._snapshot = snapshot