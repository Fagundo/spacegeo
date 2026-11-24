"""Readers for INTERMAGNET HAPI responses: 1-minute field CSV and station info JSON.

HAPI CSV rows have no header: ``time, X, Y, Z`` (nT, geographic north/east/
down), time stamps at the start of each minute (``timeStampLocation: begin``),
fill value 99999.0. Reference: https://imag-data.bgs.ac.uk/GIN_V1/hapi.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Self

import pandas as pd

from spacegeo.common.exceptions import SchemaError
from spacegeo.common.geo import normalize_longitude
from spacegeo.common.time import to_utc
from spacegeo.common.validation import ColumnSpec, TableSchema
from spacegeo.data.io.base import READERS, DatasetReader


@READERS.register("intermagnet")
class IntermagnetReader(DatasetReader):
    """Parses 1-minute X/Y/Z observatory data (nT) into a UTC minute-indexed frame."""

    N_COLUMNS = 4
    FILL = 99999.0

    fill_values: ClassVar[dict[str, tuple[float, ...]]] = {
        "x_nT": (FILL,),
        "y_nT": (FILL,),
        "z_nT": (FILL,),
    }

    schema = TableSchema(
        columns=(
            ColumnSpec("x_nT", min_value=-70000, max_value=70000),
            ColumnSpec("y_nT", min_value=-70000, max_value=70000),
            ColumnSpec("z_nT", min_value=-70000, max_value=70000),
        )
    )

    def _parse(self, path: Path) -> pd.DataFrame:
        if path.stat().st_size == 0:  # HAPI answers "no data" with an empty body
            empty = pd.DataFrame(columns=["x_nT", "y_nT", "z_nT"], dtype=float)
            empty.index = pd.DatetimeIndex([], tz="UTC", name="time")
            return empty
        raw = pd.read_csv(path, header=None, dtype={0: str})
        if raw.shape[1] != self.N_COLUMNS:
            raise SchemaError(
                f"{path.name}: expected {self.N_COLUMNS} HAPI columns (time, X, Y, Z), "
                f"got {raw.shape[1]}."
            )
        out = pd.DataFrame(raw.iloc[:, 1:].to_numpy(dtype=float), columns=["x_nT", "y_nT", "z_nT"])
        out.index = pd.DatetimeIndex(pd.to_datetime(raw[0], utc=True, format="ISO8601"))
        out.index.name = "time"
        return out


@dataclass(frozen=True)
class IntermagnetStation:
    """Observatory metadata from a HAPI ``info`` document.

    Attributes:
        code: IAGA code (upper case).
        name: Observatory name.
        lat_deg: Geographic latitude, degrees.
        lon_deg: Geographic longitude, degrees in [-180, 180).
        start: First available time, UTC.
        stop: Last available time, UTC.
    """

    code: str
    name: str
    lat_deg: float
    lon_deg: float
    start: pd.Timestamp
    stop: pd.Timestamp

    @classmethod
    def from_info(cls, code: str, path: Path) -> Self:
        """Parse an info JSON; fails loudly if coordinates are missing."""
        info = json.loads(path.read_text())
        try:
            lat, lon = float(info["x_latitude"]), float(info["x_longitude"])
            start = to_utc(info["startDate"])
            stop = to_utc(info["stopDate"])
        except KeyError as err:
            raise SchemaError(f"{path.name}: info lacks {err}.") from err
        return cls(
            code=code.upper(),
            name=str(info.get("description", info.get("x_description", code.upper()))),
            lat_deg=lat,
            lon_deg=float(normalize_longitude(lon)),
            start=start,
            stop=stop,
        )

    def to_dict(self) -> dict[str, object]:
        """JSON-ready form (written next to the station's archive)."""
        return {
            "code": self.code,
            "name": self.name,
            "lat_deg": self.lat_deg,
            "lon_deg": self.lon_deg,
            "start": self.start.isoformat(),
            "stop": self.stop.isoformat(),
        }
