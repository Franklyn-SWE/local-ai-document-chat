"""
Purpose:
    Safely discovers and loads supported UTF-8 documents from the configured
    corpus directory while isolating invalid or unsafe files.

Place in the system:
    This module is the filesystem trust boundary. It converts files under the
    configured data root into validated SourceDocument objects before any text
    is passed to chunking, retrieval, or the language model.
"""

from pathlib import Path

from app.corpus.models import CorpusIssue, CorpusLoadResult, SourceDocument

SUPPORTED_SUFFIXES = frozenset({".txt", ".md"})


class CorpusRootError(RuntimeError):
    """Raised when the configured corpus root itself is unusable."""


def _is_hidden(relative_path: Path) -> bool:
    """Return True when any component of a relative path is hidden."""
    return any(part.startswith(".") for part in relative_path.parts)


def load_corpus(data_dir: str | Path) -> CorpusLoadResult:
    """Load supported documents from a corpus root without failing on bad files."""
    root = Path(data_dir)

    if not root.exists():
        raise CorpusRootError(f"Corpus directory does not exist: {root}")

    if not root.is_dir():
        raise CorpusRootError(f"Corpus path is not a directory: {root}")

    resolved_root = root.resolve()

    documents: list[SourceDocument] = []
    issues: list[CorpusIssue] = []

    for candidate in sorted(root.rglob("*")):
        relative_path = candidate.relative_to(root)

        if candidate.is_symlink():
            issues.append(
                CorpusIssue(
                    path=relative_path.as_posix(),
                    reason="symbolic_link_rejected",
                )
            )
            continue

        if not candidate.is_file():
            continue

        if _is_hidden(relative_path):
            issues.append(
                CorpusIssue(
                    path=relative_path.as_posix(),
                    reason="hidden_file_rejected",
                )
            )
            continue

        if candidate.suffix.lower() not in SUPPORTED_SUFFIXES:
            issues.append(
                CorpusIssue(
                    path=relative_path.as_posix(),
                    reason="unsupported_file_type",
                )
            )
            continue

        try:
            resolved_candidate = candidate.resolve(strict=True)
        except OSError:
            issues.append(
                CorpusIssue(
                    path=relative_path.as_posix(),
                    reason="file_resolution_failed",
                )
            )
            continue

        if not resolved_candidate.is_relative_to(resolved_root):
            issues.append(
                CorpusIssue(
                    path=relative_path.as_posix(),
                    reason="outside_data_boundary",
                )
            )
            continue

        try:
            content = resolved_candidate.read_text(
                encoding="utf-8",
                errors="strict",
            )
        except UnicodeDecodeError:
            issues.append(
                CorpusIssue(
                    path=relative_path.as_posix(),
                    reason="invalid_utf8",
                )
            )
            continue
        except OSError:
            issues.append(
                CorpusIssue(
                    path=relative_path.as_posix(),
                    reason="file_read_failed",
                )
            )
            continue

        documents.append(
            SourceDocument(
                relative_path=relative_path.as_posix(),
                content=content,
            )
        )

    return CorpusLoadResult(
        documents=tuple(documents),
        issues=tuple(issues),
    )