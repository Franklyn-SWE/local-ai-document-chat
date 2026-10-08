"""
Purpose:
    Verifies lexical ranking, relevance thresholds, top-k limits, and explicit
    context-budget behaviour.

Place in the system:
    These tests protect the evidence-selection contract used by later prompt
    assembly and model inference.
"""

from app.corpus.models import DocumentChunk
from app.retrieval.bm25 import retrieve


def _chunk(
    chunk_id: str,
    text: str,
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        source=chunk_id.split("#", maxsplit=1)[0],
        index=0,
        text=text,
    )


def test_relevant_chunk_is_ranked_first() -> None:
    chunks = (
        _chunk(
            "leave.md#chunk-0000",
            "Employees receive 25 days annual leave each year.",
        ),
        _chunk(
            "remote.md#chunk-0000",
            "Employees may work remotely for two days each week.",
        ),
    )

    result = retrieve(
        "How many days can employees work remotely?",
        chunks,
        top_k=8,
        min_score=0.10,
        token_budget=500,
    )

    assert result.insufficient_evidence is False
    assert result.selected[0].chunk.chunk_id == "remote.md#chunk-0000"


def test_irrelevant_query_returns_insufficient_evidence() -> None:
    chunks = (
        _chunk(
            "policy.md#chunk-0000",
            "Employees receive 25 days annual leave.",
        ),
    )

    result = retrieve(
        "What is the office Wi-Fi password?",
        chunks,
        top_k=8,
        min_score=0.10,
        token_budget=500,
    )

    assert result.insufficient_evidence is True
    assert result.selected == ()


def test_top_k_limits_candidates() -> None:
    chunks = tuple(
        _chunk(
            f"policy-{index}.md#chunk-0000",
            "Remote work policy applies to employees.",
        )
        for index in range(5)
    )

    result = retrieve(
        "remote work policy",
        chunks,
        top_k=2,
        min_score=0.0,
        token_budget=500,
    )

    assert len(result.candidates) == 2


def test_context_budget_excludes_chunks_deliberately() -> None:
    chunks = (
        _chunk(
            "one.md#chunk-0000",
            "remote " * 120,
        ),
        _chunk(
            "two.md#chunk-0000",
            "remote " * 120,
        ),
    )

    result = retrieve(
        "remote",
        chunks,
        top_k=2,
        min_score=0.0,
        token_budget=220,
    )

    assert len(result.candidates) == 2
    assert len(result.selected) == 1
    assert result.excluded_by_budget == 1
    assert result.estimated_context_tokens <= result.token_budget


def test_selected_chunk_ids_are_exposed() -> None:
    chunks = (
        _chunk(
            "policy.md#chunk-0000",
            "Remote work is permitted.",
        ),
    )

    result = retrieve(
        "remote work",
        chunks,
        top_k=8,
        min_score=0.0,
        token_budget=500,
    )

    assert result.selected_chunk_ids == (
        "policy.md#chunk-0000",
    )

def test_partial_overlap_does_not_become_sufficient_evidence() -> None:
    """
    Reject a chunk that shares incidental words but not the query's subject.

    This protects against a small corpus treating the remote-work policy as
    annual-leave evidence merely because both texts contain words such as
    "days" or "per".
    """
    chunks = (
        _chunk(
            "remote-policy.md#chunk-0000",
            "Remote work is permitted up to two days per week "
            "with manager approval.",
        ),
    )

    result = retrieve(
        "How many days of paid annual leave are employees entitled to per year?",
        chunks,
        top_k=8,
        min_score=0.10,
        token_budget=500,
    )

    assert result.insufficient_evidence is True
    assert result.selected == ()