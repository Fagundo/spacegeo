"""Reader for USGS ComCat FDSN CSV exports."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pandas as pd

from spacegeo.common.exceptions import SchemaError
from spacegeo.common.geo import normalize_longitude
from spacegeo.common.validation import ColumnSpec, TableSchema
from spacegeo.data.io.base import READERS, DatasetReader


@READERS.register("comcat")
class ComCatReader(DatasetReader):
    """Parses ComCat CSV into a UTC-indexed event catalog.

    Output columns: ``lat_deg``, ``lon_deg`` (degrees, lon in [-180, 180)),
    ``depth_km`` (km, positive down; slightly negative is above sea level),
    ``mag`` (magnitude, mixed types as reported), ``mag_type``, ``event_id``.
    """

    RENAME: ClassVar[dict[str, str]] = {
        "latitude": "lat_deg",
        "longitude": "lon_deg",
        "depth": "depth_km",
        "mag": "mag",
        "magType": "mag_type",
        "id": "event_id",
    }

    schema = TableSchema(
        columns=(
            ColumnSpec("lat_deg", min_value=-90, max_value=90, nullable=False),
            ColumnSpec("lon_deg", min_value=-180, max_value=180, nullable=False),
            ColumnSpec("depth_km", min_value=-15, max_value=800),
            ColumnSpec("mag", min_value=-2, max_value=10.5),
            ColumnSpec("mag_type", kind="str"),
            ColumnSpec("event_id", kind="str", nullable=False),
        )
    )

    TRUNCATION_ROWS = 20000
    """USGS FDSN per-query limit: a file this long was probably cut off."""

    def _parse(self, path: Path) -> pd.DataFrame:
        raw = pd.read_csv(path, dtype={"magType": "string", "id": "string"})
        if len(raw) >= self.TRUNCATION_ROWS:
            raise SchemaError(
                f"{path.name}: {len(raw)} rows hits the service limit; use smaller download chunks."
            )
        missing = sorted({"time", *self.RENAME} - set(raw.columns))
        if missing:
            raise SchemaError(f"{path.name}: ComCat CSV is missing columns {missing}.")
        out = raw.filter(items=list(self.RENAME)).rename(columns=self.RENAME)
        out["lon_deg"] = normalize_longitude(out["lon_deg"].to_numpy())
        out["mag_type"] = out["mag_type"].astype(object)
        out["event_id"] = out["event_id"].astype(object)
        out.index = pd.DatetimeIndex(pd.to_datetime(raw["time"], utc=True, format="ISO8601"))
        out.index.name = "time"
        return out
