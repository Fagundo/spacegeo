"""Canonical project paths, so no module hard-codes a directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    """Resolved locations of project directories.

    Attributes:
        root: Repository root (the directory holding ``pyproject.toml``).
    """

    root: Path

    @classmethod
    def discover(cls, start: Path | None = None) -> ProjectPaths:
        """Walk upward from ``start`` (default: cwd) to find the repo root."""
        here = (start or Path.cwd()).resolve()
        for candidate in (here, *here.parents):
            if (candidate / "pyproject.toml").exists():
                return cls(root=candidate)
        raise FileNotFoundError(f"No pyproject.toml found above {here}.")

    @property
    def data_raw(self) -> Path:
        """Immutable raw downloads (gitignored)."""
        return self.root / "data" / "raw"

    @property
    def data_processed(self) -> Path:
        """Regenerable processed data (gitignored)."""
        return self.root / "data" / "processed"

    @property
    def runs(self) -> Path:
        """Experiment run outputs (gitignored)."""
        return self.root / "runs"

    @property
    def configs(self) -> Path:
        """Experiment configs (committed)."""
        return self.root / "configs"

    def raw_source(self, source_name: str) -> Path:
        """Raw directory for one data source."""
        return self.data_raw / source_name
