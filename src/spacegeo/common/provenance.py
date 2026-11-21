"""Provenance records for raw downloads: where a file came from, when, and its hash."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


def sha256_file(path: Path, chunk_bytes: int = 1 << 20) -> str:
    """Return the hex SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ProvenanceRecord:
    """One downloaded file.

    Attributes:
        url: Source URL.
        filename: File name relative to the source's raw directory.
        sha256: Hex SHA-256 of the file as downloaded.
        retrieved_at: ISO-8601 UTC timestamp of retrieval.
    """

    url: str
    filename: str
    sha256: str
    retrieved_at: str


class ProvenanceLog:
    """Append-only ``PROVENANCE.json`` for one raw-data directory."""

    FILENAME = "PROVENANCE.json"

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    @property
    def path(self) -> Path:
        """Location of the JSON log."""
        return self._directory / self.FILENAME

    def records(self) -> list[ProvenanceRecord]:
        """All records, oldest first."""
        if not self.path.exists():
            return []
        return [ProvenanceRecord(**item) for item in json.loads(self.path.read_text())]

    def latest(self, filename: str) -> ProvenanceRecord | None:
        """Most recent record for ``filename``, if any."""
        matches = [r for r in self.records() if r.filename == filename]
        return matches[-1] if matches else None

    def record(self, url: str, file: Path) -> ProvenanceRecord:
        """Hash ``file`` and append a record for it."""
        entry = ProvenanceRecord(
            url=url,
            filename=file.name,
            sha256=sha256_file(file),
            retrieved_at=datetime.now(UTC).isoformat(),
        )
        self._directory.mkdir(parents=True, exist_ok=True)
        payload = [asdict(r) for r in [*self.records(), entry]]
        self.path.write_text(json.dumps(payload, indent=2) + "\n")
        return entry

    def is_current(self, file: Path) -> bool:
        """Whether ``file`` exists and matches its latest recorded hash."""
        entry = self.latest(file.name)
        return entry is not None and file.exists() and sha256_file(file) == entry.sha256
