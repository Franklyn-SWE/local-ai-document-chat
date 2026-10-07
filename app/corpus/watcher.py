"""
Purpose:
    Detects relevant runtime corpus changes and promotes stable changes into a
    new immutable corpus snapshot.

Place in the system:
    This module watches the configured corpus directory and connects filesystem
    changes to CorpusState without requiring an application restart or manual
    re-index operation.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

from app.corpus.loader import SUPPORTED_SUFFIXES
from app.corpus.state import CorpusState, build_snapshot


@dataclass(frozen=True, slots=True)
class FileSignature:
    """Filesystem metadata used to detect relevant corpus changes."""

    relative_path: str
    size: int
    modified_ns: int


def scan_signature(data_dir: str | Path) -> tuple[FileSignature, ...]:
    """Return deterministic metadata for supported, non-hidden corpus files."""
    root = Path(data_dir)

    if not root.exists() or not root.is_dir():
        return ()

    signatures: list[FileSignature] = []

    for candidate in sorted(root.rglob("*")):
        relative_path = candidate.relative_to(root)

        if candidate.is_symlink() or not candidate.is_file():
            continue

        if any(part.startswith(".") for part in relative_path.parts):
            continue

        if candidate.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue

        try:
            stat = candidate.stat()
        except OSError:
            continue

        signatures.append(
            FileSignature(
                relative_path=relative_path.as_posix(),
                size=stat.st_size,
                modified_ns=stat.st_mtime_ns,
            )
        )

    return tuple(signatures)


class CorpusWatcher:
    """Poll the corpus and promote only stable filesystem changes."""

    def __init__(
        self,
        *,
        data_dir: str | Path,
        state: CorpusState,
        chunk_size: int,
        overlap: int,
        poll_interval_seconds: float,
        stability_delay_seconds: float,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._state = state
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._poll_interval_seconds = poll_interval_seconds
        self._stability_delay_seconds = stability_delay_seconds

        self._active_signature = scan_signature(self._data_dir)

        self._pending_signature: tuple[FileSignature, ...] | None = None
        self._pending_since: float | None = None

    def poll_once(self, *, now: float | None = None) -> bool:
        """
        Inspect the filesystem once.

        Return True only when a stable change is promoted into active state.
        """
        current_signature = scan_signature(self._data_dir)

        if current_signature == self._active_signature:
            self._pending_signature = None
            self._pending_since = None
            return False

        current_time = monotonic() if now is None else now

        if current_signature != self._pending_signature:
            self._pending_signature = current_signature
            self._pending_since = current_time
            return False

        if self._pending_since is None:
            self._pending_since = current_time
            return False

        if current_time - self._pending_since < self._stability_delay_seconds:
            return False

        snapshot = build_snapshot(
            self._data_dir,
            chunk_size=self._chunk_size,
            overlap=self._overlap,
        )

        self._state.replace(snapshot)
        self._active_signature = current_signature

        self._pending_signature = None
        self._pending_since = None

        return True

    async def run(self) -> None:
        """Continuously poll until the task is cancelled."""
        while True:
            self.poll_once()
            await asyncio.sleep(self._poll_interval_seconds)