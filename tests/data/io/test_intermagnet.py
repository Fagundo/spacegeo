from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from spacegeo.common.exceptions import SchemaError
from spacegeo.common.time import to_utc
from spacegeo.data.io.intermagnet import IntermagnetReader, IntermagnetStation

FIXTURES = Path(__file__).parents[2] / "fixtures" / "intermagnet"


def test_parses_minutes_and_fill() -> None:
    df = IntermagnetReader().read([FIXTURES / "CMO_sample.csv"])
    index = pd.DatetimeIndex(df.index)
    assert str(index.tz) == "UTC"
    assert len(df) == 150
    assert index[0] == to_utc("2024-05-10T22:00Z")
    assert list(df.columns) == ["x_nT", "y_nT", "z_nT"]
    assert np.isnan(df["x_nT"].to_numpy()[70])
    assert np.isfinite(df["x_nT"].to_numpy()[69])


def test_wrong_columns_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("2024-05-10T22:00Z,1.0,2.0\n")
    with pytest.raises(SchemaError, match="4 HAPI columns"):
        IntermagnetReader().read([bad])


def test_station_info() -> None:
    station = IntermagnetStation.from_info("cmo", FIXTURES / "CMO_info.json")
    assert station.code == "CMO"
    assert station.lat_deg == pytest.approx(64.87)
    assert station.lon_deg == pytest.approx(212.14 - 360)
    assert station.start == to_utc("1991-01-01T00:00Z")
    assert station.to_dict()["lon_deg"] == pytest.approx(-147.86)


def test_station_info_without_coordinates_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "info.json"
    bad.write_text('{"startDate": "1991-01-01T00:00:00Z"}')
    with pytest.raises(SchemaError, match="x_latitude"):
        IntermagnetStation.from_info("CMO", bad)


def test_empty_response_is_empty_frame(tmp_path: Path) -> None:
    empty = tmp_path / "PMG_2020.csv"
    empty.write_text("")
    df = IntermagnetReader().read([empty])
    assert df.empty
    assert list(df.columns) == ["x_nT", "y_nT", "z_nT"]
