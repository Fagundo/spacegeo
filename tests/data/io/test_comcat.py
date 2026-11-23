from pathlib import Path

import pandas as pd
import pytest

from spacegeo.common.exceptions import SchemaError
from spacegeo.data.io.comcat import ComCatReader

FIXTURE = Path(__file__).parents[2] / "fixtures" / "comcat" / "sample.csv"


def test_parses_sorted_utc_catalog() -> None:
    df = ComCatReader().read([FIXTURE])
    assert str(pd.DatetimeIndex(df.index).tz) == "UTC"
    assert df.index.is_monotonic_increasing
    assert list(df.columns) == ["lat_deg", "lon_deg", "depth_km", "mag", "mag_type", "event_id"]
    assert df["event_id"].iloc[0] == "us7000a002"


def test_longitude_180_wraps_and_missing_mag_is_nan() -> None:
    df = ComCatReader().read([FIXTURE]).set_index("event_id")
    assert df.loc["us7000a003", "lon_deg"] == -180.0
    assert df.loc[["us7000a003"], "mag"].isna().all()


def test_bad_latitude_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text(FIXTURE.read_text().replace("-17.8123", "-97.8123"))
    with pytest.raises(SchemaError, match="lat_deg"):
        ComCatReader().read([bad])


def test_missing_column_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("time,latitude\n2026-01-01T00:00:00Z,1.0\n")
    with pytest.raises(SchemaError, match="missing columns"):
        ComCatReader().read([bad])


def test_truncated_file_rejected(tmp_path: Path) -> None:
    lines = FIXTURE.read_text().splitlines()
    bad = tmp_path / "big.csv"
    bad.write_text("\n".join([lines[0]] + [lines[1]] * ComCatReader.TRUNCATION_ROWS) + "\n")
    with pytest.raises(SchemaError, match="service limit"):
        ComCatReader().read([bad])
