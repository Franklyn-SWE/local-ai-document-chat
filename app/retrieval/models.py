"""
Purpose:
    Defines the data structures used to represent ranked evidence and the final
    context selection passed to later prompt assembly.

Place in the system:
    These models form the contract between corpus retrieval, context budgeting,
    prompt assembly, diagnostics, and observability.
"""

from dataclasses import dataclass

from app.corpus.models import DocumentChunk


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    """One corpus chunk with its lexical relevance score."""

    chunk: DocumentChunk
    score: float


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """The deliberate evidence selection produced for one user question."""

    candidates: tuple[ScoredChunk, ...]
    selected: tuple[ScoredChunk, ...]
    excluded_by_budget: int
    estimated_context_tokens: int
    token_budget: int
    insufficient_evidence: bool

    @property
    def selected_chunk_ids(self) -> tuple[str, ...]:
        """Return stable identifiers for selected evidence."""
        return tuple(item.chunk.chunk_id for item in self.selected)