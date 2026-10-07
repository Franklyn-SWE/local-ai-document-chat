"""
Purpose:
    Verifies immutable corpus snapshot construction, versioning, and state
    replacement behaviour.

Place in the system:
    These tests protect the consistency boundary used by later request
    processing and live corpus refresh.
"""

from pathlib import Path

from app.corpus.state import CorpusState, build_snapshot


def test_snapshot_contains_documents_chunks_and_version(
    tmp_path: Path,
) -> None:
    (tmp_path / "policy.md").write_text(
        "Remote work is permitted.",
        encoding="utf-8",
    )

    snapshot = build_snapshot(
        tmp_path,
        chunk_size=100,
        overlap=20,
    )

    assert snapshot.file_count == 1
    assert snapshot.chunk_count == 1
    assert len(snapshot.version) == 12


def test_snapshot_version_changes_when_content_changes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "policy.md"

    path.write_text(
        "Remote work is two days.",
        encoding="utf-8",
    )

    first = build_snapshot(
        tmp_path,
        chunk_size=100,
        overlap=20,
    )

    path.write_text(
        "Remote work is three days.",
        encoding="utf-8",
    )

    second = build_snapshot(
        tmp_path,
        chunk_size=100,
        overlap=20,
    )

    assert first.version != second.version


def test_corpus_state_replaces_complete_snapshot(
    tmp_path: Path,
) -> None:
    path = tmp_path / "policy.md"

    path.write_text(
        "Version one.",
        encoding="utf-8",
    )

    first = build_snapshot(
        tmp_path,
        chunk_size=100,
        overlap=20,
    )

    state = CorpusState(first)

    path.write_text(
        "Version two.",
        encoding="utf-8",
    )

    second = build_snapshot(
        tmp_path,
        chunk_size=100,
        overlap=20,
    )

    state.replace(second)

    active = state.get_snapshot()

    assert active.version == second.version
    assert active.chunks[0].text == "Version two."