"""
Purpose:
    Verifies deterministic document chunking and configuration validation.

Place in the system:
    These unit tests protect the contract between corpus ingestion and later
    retrieval by checking chunk boundaries, overlap, and stable identifiers.
"""

import pytest

from app.corpus.chunker import chunk_document
from app.corpus.models import SourceDocument


def test_short_document_produces_one_chunk() -> None:
    document = SourceDocument(
        relative_path="policy.md",
        content="Employees receive 25 days annual leave.",
    )

    chunks = chunk_document(document, chunk_size=100, overlap=20)

    assert len(chunks) == 1
    assert chunks[0].chunk_id == "policy.md#chunk-0000"
    assert chunks[0].source == "policy.md"
    assert chunks[0].text == "Employees receive 25 days annual leave."


def test_long_document_produces_overlapping_chunks() -> None:
    document = SourceDocument(
        relative_path="handbook.txt",
        content="ABCDEFGHIJ",
    )

    chunks = chunk_document(document, chunk_size=6, overlap=2)

    assert [chunk.text for chunk in chunks] == [
        "ABCDEF",
        "EFGHIJ",
    ]


def test_empty_document_produces_no_chunks() -> None:
    document = SourceDocument(
        relative_path="empty.md",
        content="   ",
    )

    assert chunk_document(document) == ()


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [
        (0, 0),
        (-1, 0),
        (100, -1),
        (100, 100),
        (100, 101),
    ],
)
def test_invalid_chunk_configuration_is_rejected(
    chunk_size: int,
    overlap: int,
) -> None:
    document = SourceDocument(
        relative_path="policy.md",
        content="content",
    )

    with pytest.raises(ValueError):
        chunk_document(
            document,
            chunk_size=chunk_size,
            overlap=overlap,
        )