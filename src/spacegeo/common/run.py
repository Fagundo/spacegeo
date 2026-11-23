"""Experiment run directories: one folder per run with its provenance."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class GitState:
    """Commit and cleanliness of the working tree.

    Attributes:
        commit: Full commit hash, or ``unknown`` outside a git checkout.
        dirty: Whether tracked or untracked files differ from the commit.
    """

    commit: str
    dirty: bool

    @classmethod
    def read(cls, root: Path) -> GitState:
        """Inspect the repository at ``root``."""
        head = cls._git(root, "rev-parse", "HEAD")
        status = cls._git(root, "status", "--porcelain")
        return cls(commit=head or "unknown", dirty=bool(status))

    @staticmethod
    def _git(root: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=False
        )
        return result.stdout.strip() if result.returncode == 0 else ""


class RunDirectory:
    """``runs/<UTC-timestamp>_<slug>/`` with git state and seed recorded.

    Args:
        runs_root: Parent directory (``ProjectPaths.runs``).
        slug: Short name of the experiment.
        git: Repository state at launch.
        seed: Random seed used.
    """

    def __init__(self, runs_root: Path, slug: str, git: GitState, seed: int) -> None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self._path = runs_root / f"{stamp}_{slug}"
        self._path.mkdir(parents=True)
        dirty = " (dirty working tree)" if git.dirty else ""
        self.write_text("git.txt", f"{git.commit}{dirty}\n")
        self.write_text("seed.txt", f"{seed}\n")

    @property
    def path(self) -> Path:
        """The run directory."""
        return self._path

    def write_text(self, name: str, text: str) -> Path:
        """Write a text file into the run directory."""
        target = self._path / name
        target.write_text(text)
        return target

    def write_frame(self, name: str, frame: pd.DataFrame, *, index: bool = False) -> Path:
        """Write a CSV (gzipped deterministically if ``name`` ends in ``.gz``)."""
        target = self._path / name
        compression = {"method": "gzip", "mtime": 0} if name.endswith(".gz") else None
        frame.to_csv(target, index=index, float_format="%.6g", compression=compression)
        return target

    def write_json(self, name: str, payload: object) -> Path:
        """Write JSON (sorted keys, two-space indent)."""
        return self.write_text(name, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def markdown_table(frame: pd.DataFrame, *, index_name: str | None = None) -> str:
    """A GitHub-flavoured Markdown table (floats to 4 significant figures).

    Args:
        frame: Table to render.
        index_name: Header for the index column; ``None`` leaves the index out.
    """
    columns = [str(c) for c in frame.columns]
    header = ([index_name] if index_name is not None else []) + columns
    rows = []
    for label, values in zip(frame.index, frame.itertuples(index=False), strict=True):
        cells = [f"{v:.4g}" if isinstance(v, float) else str(v) for v in values]
        rows.append("| " + " | ".join(([str(label)] if index_name else []) + cells) + " |")
    rule = "|" + "---|" * len(header)
    return "\n".join(["| " + " | ".join(header) + " |", rule, *rows])
