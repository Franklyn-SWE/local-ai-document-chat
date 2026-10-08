"""
Purpose:
    Ranks corpus chunks against a user question using a small deterministic
    BM25-style lexical scorer and applies an explicit context budget.

Place in the system:
    This module sits between the active corpus snapshot and prompt assembly.
    It selects evidence only; it does not call the language model.
"""

import math
import re
from collections import Counter

from app.corpus.models import DocumentChunk
from app.retrieval.models import RetrievalResult, ScoredChunk

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
# Common query words carry little evidence value. Excluding them from the
# coverage check prevents a chunk being accepted only because it contains
# generic language such as "the", "is", or "company".
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "company",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


def _tokenize(text: str) -> list[str]:
    """Normalise text into lowercase lexical tokens."""
    return _TOKEN_PATTERN.findall(text.lower())

def _has_meaningful_overlap(
    query: str,
    chunk_text: str,
) -> bool:
    """
    Require sufficient meaningful query coverage before accepting evidence.

    BM25 ranks the best available chunks, but in a small corpus the highest
    ranked chunk can still be unrelated. This gate therefore checks how much
    of the meaningful query vocabulary is actually represented in the chunk.
    """
    query_terms = {
        token
        for token in _tokenize(query)
        if token not in _STOP_WORDS
    }

    if not query_terms:
        return False

    chunk_terms = set(_tokenize(chunk_text))
    matching_terms = query_terms & chunk_terms

    # Short queries need at least one meaningful lexical match. For longer
    # queries, require enough query coverage to reject incidental overlap
    # such as sharing only generic terms like "days" and "per".
    if len(query_terms) <= 2:
        return len(matching_terms) >= 1

    coverage = len(matching_terms) / len(query_terms)

    return coverage >= 0.40


def _estimate_tokens(text: str) -> int:
    """
    Estimate token count conservatively for context budgeting.

    The method uses approximately four characters per token and is labelled
    as an estimate until model-reported usage is available.
    """
    return max(1, math.ceil(len(text) / 4))


def _score_chunks(
    query: str,
    chunks: tuple[DocumentChunk, ...],
) -> tuple[ScoredChunk, ...]:
    """Return corpus chunks ordered by descending BM25-style relevance."""
    query_tokens = _tokenize(query)

    if not query_tokens or not chunks:
        return ()

    tokenised_chunks = [_tokenize(chunk.text) for chunk in chunks]

    document_count = len(tokenised_chunks)

    average_length = (
        sum(len(tokens) for tokens in tokenised_chunks) / document_count
    )

    document_frequency: Counter[str] = Counter()

    for tokens in tokenised_chunks:
        document_frequency.update(set(tokens))

    k1 = 1.5
    b = 0.75

    scored: list[ScoredChunk] = []

    for chunk, tokens in zip(chunks, tokenised_chunks, strict=True):
        frequencies = Counter(tokens)
        length = len(tokens)

        score = 0.0

        for term in query_tokens:
            frequency = frequencies.get(term, 0)

            if frequency == 0:
                continue

            df = document_frequency[term]

            idf = math.log(
                1 + (document_count - df + 0.5) / (df + 0.5)
            )

            denominator = frequency + k1 * (
                1 - b + b * (length / average_length)
            )

            score += idf * (
                frequency * (k1 + 1) / denominator
            )

        if score > 0:
            scored.append(
                ScoredChunk(
                    chunk=chunk,
                    score=score,
                )
            )

    return tuple(
        sorted(
            scored,
            key=lambda item: (-item.score, item.chunk.chunk_id),
        )
    )


def retrieve(
    query: str,
    chunks: tuple[DocumentChunk, ...],
    *,
    top_k: int,
    min_score: float,
    token_budget: int,
) -> RetrievalResult:
    """Rank evidence and select only chunks that fit within the context budget."""
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")

    if min_score < 0:
        raise ValueError("min_score must not be negative")

    if token_budget <= 0:
        raise ValueError("token_budget must be greater than zero")

    ranked = _score_chunks(query, chunks)

    # Ranking alone does not prove that evidence is sufficient. In a tiny corpus,
# BM25 can still return a "best" chunk even when the question is unrelated.
# Require both the configured score and meaningful lexical query coverage.
    candidates = tuple(
        item
        for item in ranked[:top_k]
        if item.score >= min_score
        and _has_meaningful_overlap(query, item.chunk.text)
    )


    selected: list[ScoredChunk] = []
    estimated_context_tokens = 0
    excluded_by_budget = 0

    for item in candidates:
        chunk_tokens = _estimate_tokens(item.chunk.text)

        if estimated_context_tokens + chunk_tokens > token_budget:
            excluded_by_budget += 1
            continue

        selected.append(item)
        estimated_context_tokens += chunk_tokens

    return RetrievalResult(
        candidates=candidates,
        selected=tuple(selected),
        excluded_by_budget=excluded_by_budget,
        estimated_context_tokens=estimated_context_tokens,
        token_budget=token_budget,
        insufficient_evidence=len(selected) == 0,
    )