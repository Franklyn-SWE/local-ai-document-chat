"""
Purpose:
    Verifies that added, modified, renamed, and removed documents are promoted
    into subsequent corpus snapshots without restarting the application.

Place in the system:
    This integration test exercises the core live-corpus behaviour required by
    the assessment.
"""

from pathlib import Path

from app.corpus.state import CorpusState, build_snapshot
from app.corpus.watcher import CorpusWatcher


def _build_watcher(
    tmp_path: Path,
) -> tuple[CorpusState, CorpusWatcher]:
    initial = build_snapshot(
        tmp_path,
        chunk_size=100,
        overlap=20,
    )

    state = CorpusState(initial)

    watcher = CorpusWatcher(
        data_dir=tmp_path,
        state=state,
        chunk_size=100,
        overlap=20,
        poll_interval_seconds=1.0,
        stability_delay_seconds=0.5,
    )

    return state, watcher


def _promote_change(
    watcher: CorpusWatcher,
    *,
    start_time: float,
) -> None:
    assert watcher.poll_once(now=start_time) is False
    assert watcher.poll_once(now=start_time + 0.6) is True


def test_added_document_becomes_available(
    tmp_path: Path,
) -> None:
    state, watcher = _build_watcher(tmp_path)

    (tmp_path / "policy.md").write_text(
        "Remote work is two days.",
        encoding="utf-8",
    )

    _promote_change(watcher, start_time=1.0)

    snapshot = state.get_snapshot()

    assert snapshot.file_count == 1
    assert snapshot.chunks[0].text == "Remote work is two days."


def test_modified_document_replaces_old_content(
    tmp_path: Path,
) -> None:
    path = tmp_path / "policy.md"

    path.write_text(
        "Remote work is two days.",
        encoding="utf-8",
    )

    state, watcher = _build_watcher(tmp_path)

    path.write_text(
        "Remote work is three days.",
        encoding="utf-8",
    )

    _promote_change(watcher, start_time=2.0)

    snapshot = state.get_snapshot()

    assert snapshot.file_count == 1
    assert snapshot.chunks[0].text == "Remote work is three days."


def test_removed_document_disappears(
    tmp_path: Path,
) -> None:
    path = tmp_path / "policy.md"

    path.write_text(
        "Remote work is two days.",
        encoding="utf-8",
    )

    state, watcher = _build_watcher(tmp_path)

    path.unlink()

    _promote_change(watcher, start_time=3.0)

    snapshot = state.get_snapshot()

    assert snapshot.file_count == 0
    assert snapshot.chunk_count == 0


def test_renamed_document_replaces_old_source(
    tmp_path: Path,
) -> None:
    old_path = tmp_path / "old-policy.md"

    old_path.write_text(
        "Remote work policy.",
        encoding="utf-8",
    )

    state, watcher = _build_watcher(tmp_path)

    new_path = tmp_path / "new-policy.md"
    old_path.rename(new_path)

    _promote_change(watcher, start_time=4.0)

    snapshot = state.get_snapshot()

    assert snapshot.file_count == 1
    assert snapshot.documents[0].relative_path == "new-policy.md"
    assert snapshot.chunks[0].source == "new-policy.md"


def test_changing_file_is_not_promoted_until_stable(
    tmp_path: Path,
) -> None:
    state, watcher = _build_watcher(tmp_path)

    path = tmp_path / "policy.md"

    path.write_text(
        "Partial",
        encoding="utf-8",
    )

    assert watcher.poll_once(now=1.0) is False

    path.write_text(
        "Complete policy text.",
        encoding="utf-8",
    )

    assert watcher.poll_once(now=1.2) is False
    assert state.get_snapshot().file_count == 0

    assert watcher.poll_once(now=1.8) is True

    snapshot = state.get_snapshot()

    assert snapshot.chunks[0].text == "Complete policy text."