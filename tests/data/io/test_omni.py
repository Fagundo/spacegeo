from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from spacegeo.common.exceptions import SchemaError
from spacegeo.common.time import to_utc
from spacegeo.data.io.omni import OmniReader

FIXTURE = Path(__file__).parents[2] / "fixtures" / "omni2" / "omni2_2015.dat"


def test_parses_sorted_hourly_utc_index() -> None:
    df = OmniReader().read([FIXTURE])
    index = pd.DatetimeIndex(df.index)
    assert str(index.tz) == "UTC"
    assert index.is_monotonic_increasing
    assert list(index) == [
        to_utc("2015-01-01T00:00Z"),
        to_utc("2015-03-17T12:00Z"),
        to_utc("2015-03-17T13:00Z"),
        to_utc("2015-12-31T23:00Z"),
    ]
    assert list(df.columns) == list(OmniReader.schema.column_names)


def test_storm_hour_values_and_kp_thirds() -> None:
    row = OmniReader().read([FIXTURE]).loc[to_utc("2015-03-17T12:00Z")]
    assert row["bz_gsm_nT"] == pytest.approx(-20.3)
    assert row["speed_km_s"] == pytest.approx(561.0)
    assert row["dst_nT"] == pytest.approx(-151.0)
    assert row["kp"] == pytest.approx(6 + 2 / 3)  # OMNI code 67 = 7-


def test_fill_values_become_nan() -> None:
    df = OmniReader().read([FIXTURE])
    gap = df.loc[to_utc("2015-03-17T13:00Z")]
    for column in ("bz_gsm_nT", "speed_km_s", "density_cm3", "pdyn_nPa", "temperature_K"):
        assert np.isnan(gap[column]), column
    assert gap["dst_nT"] == pytest.approx(-40.0)
    last = df.loc[to_utc("2015-12-31T23:00Z")]
    assert np.isnan(last["kp"])
    assert np.isnan(last["dst_nT"])


def test_wrong_word_count_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "omni2_2015.dat"
    bad.write_text(FIXTURE.read_text().splitlines()[0].rsplit(" ", 1)[0] + "\n")
    with pytest.raises(SchemaError, match="55 OMNI2 words"):
        OmniReader().read([bad])


def test_out_of_range_value_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "omni2_2015.dat"
    bad.write_text(FIXTURE.read_text().replace("  561", " 5610", 1))
    with pytest.raises(SchemaError, match="speed_km_s"):
        OmniReader().read([bad])
