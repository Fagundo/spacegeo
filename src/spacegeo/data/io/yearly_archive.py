"""Committed, per-year store of a parsed, time-indexed dataset.

Unlike ``data/raw`` (gitignored downloads), the archive is meant to be
committed: one gzipped CSV per calendar year, written deterministically so an
unchanged year produces a byte-identical file and no git diff.
"""

from __future__ import annotations

import gzip
import io
from collections.abc import Hashable
from pathlib import Path
from typing import ClassVar

import pandas as pd

from spacegeo.common.provenance import ProvenanceLog
from spacegeo.common.time import TimeWindow
from spacegeo.common.validation import TableSchema


class YearlyArchive:
    """Reads and writes ``<root>/<year>.csv.gz`` files.

    Args:
        root: Archive directory (e.g. ``data/space_weather/omni2``).
        schema: Schema every stored frame must satisfy; ``str`` columns are
            restored as object dtype on read.
    """

    TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
    _DTYPES: ClassVar[dict[str, str]] = {
        "float": "float64",
        "int": "int64",
        "str": "string",
        "bool": "bool",
    }
    """Explicit dtypes so an empty year reads back with the schema's types."""

    def __init__(self, root: Path, schema: TableSchema) -> None:
        self._root = root
        self._schema = schema
        self._provenance = ProvenanceLog(root)

    @property
    def root(self) -> Path:
        """Archive directory."""
        return self._root

    def path(self, year: int) -> Path:
        """File holding ``year``'s rows."""
        return self._root / f"{year}.csv.gz"

    def years(self) -> list[int]:
        """Years present in the archive, ascending."""
        return sorted(int(p.name.split(".")[0]) for p in self._root.glob("*.csv.gz"))

    def write_year(self, year: int, rows: pd.DataFrame, source_url: str) -> bool:
        """Validate and store one year; record provenance if the file changed.

        Args:
            year: Calendar year (UTC) the rows belong to.
            rows: Rows for that year, matching the archive schema.
            source_url: Where the rows were downloaded from.

        Returns:
            Whether the stored file changed.

        Raises:
            ValueError: If any row falls outside ``year``.
        """
        self._schema.validate(rows)
        if not TimeWindow.calendar_year(year).mask(rows.index).all():
            raise ValueError(f"Rows outside {year} passed to write_year({year}).")
        payload = self._encode(rows)
        dest = self.path(year)
        if dest.exists() and dest.read_bytes() == payload:
            return False
        self._root.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        self._provenance.record(source_url, dest)
        return True

    def read(self, window: TimeWindow | None = None) -> pd.DataFrame:
        """Load all stored years (optionally only those overlapping ``window``).

        Returns:
            Validated, time-sorted rows.

        Raises:
            FileNotFoundError: If no year in range is stored.
        """
        years = [
            y
            for y in self.years()
            if window is None or TimeWindow.calendar_year(y).overlaps(window)
        ]
        if not years:
            raise FileNotFoundError(f"No years in {self._root} for {window}.")
        frames = [self._decode(self.path(y)) for y in years]
        rows = pd.concat(frames).sort_index()
        if window is not None:
            rows = rows.loc[window.mask(rows.index)]
        return self._schema.validate(rows)

    def _encode(self, rows: pd.DataFrame) -> bytes:
        frame = rows.sort_index().reset_index(names="time")
        frame["time"] = frame["time"].dt.strftime(self.TIME_FORMAT)
        text = frame.to_csv(index=False, float_format="%.6g", lineterminator="\n")
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, filename="") as handle:
            handle.write(text.encode())
        return buffer.getvalue()

    def _decode(self, path: Path) -> pd.DataFrame:
        text_columns = [spec.name for spec in self._schema.columns if spec.kind == "str"]
        dtypes: dict[Hashable, str] = {
            spec.name: self._DTYPES[spec.kind] for spec in self._schema.columns
        }
        frame = pd.read_csv(path, dtype=dtypes)
        frame.index = pd.DatetimeIndex(
            pd.to_datetime(frame.pop("time"), utc=True, format="ISO8601")
        )
        frame.index.name = "time"
        for column in text_columns:
            frame[column] = frame[column].astype(object)
        return frame.loc[:, list(self._schema.column_names)]
