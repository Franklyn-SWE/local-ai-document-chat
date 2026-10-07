"""
Purpose:
    Verifies safe corpus discovery, supported-file handling, and isolation of
    invalid document content.

Place in the system:
    These tests exercise the filesystem trust boundary before any corpus text
    reaches chunking, retrieval, prompting, or inference.
"""

from pathlib import Path

from app.corpus.loader import load_corpus


def test_loads_supported_utf8_documents(tmp_path: Path) -> None:
    (tmp_path / "policy.md").write_text(
        "Remote work is permitted.",
        encoding="utf-8",
    )
    (tmp_path / "handbook.txt").write_text(
        "Annual leave is documented here.",
        encoding="utf-8",
    )

    result = load_corpus(tmp_path)

    assert [document.relative_path for document in result.documents] == [
        "handbook.txt",
        "policy.md",
    ]
    assert result.issues == ()


def test_supports_nested_documents(tmp_path: Path) -> None:
    policies = tmp_path / "policies"
    policies.mkdir()

    (policies / "leave.md").write_text(
        "Employees receive annual leave.",
        encoding="utf-8",
    )

    result = load_corpus(tmp_path)

    assert len(result.documents) == 1
    assert result.documents[0].relative_path == "policies/leave.md"


def test_rejects_unsupported_file_type_without_failing(tmp_path: Path) -> None:
    (tmp_path / "policy.md").write_text(
        "Valid policy.",
        encoding="utf-8",
    )
    (tmp_path / "image.jpg").write_bytes(b"not-an-image")

    result = load_corpus(tmp_path)

    assert len(result.documents) == 1
    assert len(result.issues) == 1
    assert result.issues[0].path == "image.jpg"
    assert result.issues[0].reason == "unsupported_file_type"


def test_rejects_invalid_utf8_without_losing_valid_documents(tmp_path: Path) -> None:
    (tmp_path / "valid.md").write_text(
        "Valid document.",
        encoding="utf-8",
    )
    (tmp_path / "broken.txt").write_bytes(b"\xff\xfe\xfa")

    result = load_corpus(tmp_path)

    assert [document.relative_path for document in result.documents] == [
        "valid.md"
    ]
    assert len(result.issues) == 1
    assert result.issues[0].path == "broken.txt"
    assert result.issues[0].reason == "invalid_utf8"


def test_rejects_hidden_file(tmp_path: Path) -> None:
    (tmp_path / ".hidden.md").write_text(
        "Should not be loaded.",
        encoding="utf-8",
    )

    result = load_corpus(tmp_path)

    assert result.documents == ()
    assert len(result.issues) == 1
    assert result.issues[0].reason == "hidden_file_rejected"