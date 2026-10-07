"""
Purpose:
    Splits validated source documents into deterministic overlapping text chunks
    suitable for later evidence retrieval.

Place in the system:
    This module sits between safe corpus ingestion and retrieval. It does not
    access the filesystem or the language model.
"""

from app.corpus.models import DocumentChunk, SourceDocument


def chunk_document(
    document: SourceDocument,
    *,
    chunk_size: int = 1600,
    overlap: int = 200,
) -> tuple[DocumentChunk, ...]:
    """Split one source document into deterministic overlapping character chunks."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    if overlap < 0:
        raise ValueError("overlap must not be negative")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    text = document.content.strip()

    if not text:
        return ()

    step = chunk_size - overlap

    chunks: list[DocumentChunk] = []

    for index, start in enumerate(range(0, len(text), step)):
        chunk_text = text[start : start + chunk_size].strip()

        if not chunk_text:
            continue

        chunks.append(
            DocumentChunk(
                chunk_id=f"{document.relative_path}#chunk-{index:04d}",
                source=document.relative_path,
                index=index,
                text=chunk_text,
            )
        )

        if start + chunk_size >= len(text):
            break

    return tuple(chunks)


def chunk_documents(
    documents: tuple[SourceDocument, ...],
    *,
    chunk_size: int = 1600,
    overlap: int = 200,
) -> tuple[DocumentChunk, ...]:
    """Chunk a collection of validated source documents."""
    chunks: list[DocumentChunk] = []

    for document in documents:
        chunks.extend(
            chunk_document(
                document,
                chunk_size=chunk_size,
                overlap=overlap,
            )
        )

    return tuple(chunks)