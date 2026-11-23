"""Committed, per-year store of the parsed earthquake catalog.

Unlike ``data/raw`` (gitignored downloads), the archive is meant to be
committed: one gzipped CSV per calendar year, written deterministically so an
unchanged year produces a byte-identical file and no git diff.
"""

from __future__ import annotations

import gzip
import io
from pathlib import Path

import pandas as pd

from spacegeo.common.provenance import ProvenanceLog
from spacegeo.common.time import TimeWindow
from spacegeo.common.validation import TableSchema
from spacegeo.data.io.comcat import ComCatReader


class CatalogArchive:
    """Reads and writes ``<root>/<year>.csv.gz`` catalog files.

    Args:
        root: Archive directory (e.g. ``data/catalog/comcat_M4.5``).
        schema: Schema every stored frame must satisfy.
    """

    TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    def __init__(self, root: Path, schema: TableSchema = ComCatReader.schema) -> None:
        self._root = root
        self._schema = schema
        self._provenance = ProvenanceLog(root)

    @property
    def root(self) -> Path:
        """Archive directory."""
        return self._root

    def path(self, year: int) -> Path:
        """File holding ``year``'s events."""
        return self._root / f"{year}.csv.gz"

    def years(self) -> list[int]:
        """Years present in the archive, ascending."""
        return sorted(int(p.name.split(".")[0]) for p in self._root.glob("*.csv.gz"))

    def write_year(self, year: int, events: pd.DataFrame, source_url: str) -> bool:
        """Validate and store one year; record provenance if the file changed.

        Args:
            year: Calendar year (UTC) the events belong to.
            events: Catalog for that year, matching the archive schema.
            source_url: Where the events were downloaded from.

        Returns:
            Whether the stored file changed.

        Raises:
            ValueError: If any event falls outside ``year``.
        """
        self._schema.validate(events)
        if not TimeWindow.calendar_year(year).mask(events.index).all():
            raise ValueError(f"Events outside {year} passed to write_year({year}).")
        payload = self._encode(events)
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
            Validated, time-sorted catalog.

        Raises:
            FileNotFoundError: If no year in range is stored.
        """
        years = [
            y
            for y in self.years()
            if window is None or TimeWindow.calendar_year(y).overlaps(window)
        ]
        if not years:
            raise FileNotFoundError(f"No catalog years in {self._root} for {window}.")
        frames = [self._decode(self.path(y)) for y in years]
        catalog = pd.concat(frames).sort_index()
        if window is not None:
            catalog = catalog.loc[window.mask(catalog.index)]
        return self._schema.validate(catalog)

    def _encode(self, events: pd.DataFrame) -> bytes:
        frame = events.sort_index().reset_index(names="time")
        frame["time"] = frame["time"].dt.strftime(self.TIME_FORMAT)
        text = frame.to_csv(index=False, float_format="%.6g", lineterminator="\n")
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, filename="") as handle:
            handle.write(text.encode())
        return buffer.getvalue()

    def _decode(self, path: Path) -> pd.DataFrame:
        frame = pd.read_csv(path, dtype={"mag_type": "string", "event_id": "string"})
        frame.index = pd.DatetimeIndex(
            pd.to_datetime(frame.pop("time"), utc=True, format="ISO8601")
        )
        frame.index.name = "time"
        for column in ("mag_type", "event_id"):
            frame[column] = frame[column].astype(object)
        return frame.loc[:, list(self._schema.column_names)]
