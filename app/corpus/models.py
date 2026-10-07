"""
Purpose:
    Defines the immutable data structures used to represent loaded documents
    and retrieval-ready document chunks.

Place in the system:
    These models form the contract between corpus ingestion, chunking,
    retrieval, source attribution, and later observability components.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """A validated UTF-8 document loaded from the configured corpus."""

    relative_path: str
    content: str


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """A stable retrieval unit derived from one source document."""

    chunk_id: str
    source: str
    index: int
    text: str
    
@dataclass(frozen=True, slots=True)
class CorpusIssue:
    """A non-fatal problem encountered while loading one corpus file."""

    path: str
    reason: str


@dataclass(frozen=True, slots=True)
class CorpusLoadResult:
    """The valid documents and non-fatal issues found during one corpus scan."""

    documents: tuple[SourceDocument, ...]
    issues: tuple[CorpusIssue, ...]