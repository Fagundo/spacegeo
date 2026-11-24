from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from spacegeo.common.time import to_utc
from spacegeo.data.io.intermagnet import IntermagnetReader
from spacegeo.data.preprocessing.hourly_dbdt import HourlyHorizontalDbDt

FIXTURE = Path(__file__).parents[2] / "fixtures" / "intermagnet" / "CMO_sample.csv"


def _minutes(x: list[float], y: list[float], start: str = "2024-01-01T00:00Z") -> pd.DataFrame:
    index = pd.date_range(start, periods=len(x), freq="min", tz="UTC")
    return pd.DataFrame({"x_nT": x, "y_nT": y, "z_nT": 0.0}, index=index)


def test_rate_is_horizontal_vector_change_per_minute() -> None:
    x = [0.0] * 60
    y = [0.0] * 60
    x[10], y[10] = 3.0, 4.0  # 5 nT/min into minute 10 and back out of it
    out = HourlyHorizontalDbDt(min_pairs=30).transform(_minutes(x, y))
    row = out.to_dict("records")[0]
    assert row["dbh_dt_max_nT_min"] == pytest.approx(5.0)
    assert row["dbh_dt_mean_nT_min"] == pytest.approx(10.0 / 59)
    assert row["n_pairs"] == 59


def test_pairs_never_cross_hours_and_gaps_skip() -> None:
    x = [float(v) for v in range(120)]
    out = HourlyHorizontalDbDt(min_pairs=30).transform(_minutes(x, [0.0] * 120))
    assert out["n_pairs"].tolist() == [59.0, 59.0]  # the 00:59 -> 01:00 pair is dropped
    gappy = _minutes(x, [0.0] * 120).drop(
        index=pd.date_range("2024-01-01T01:00Z", periods=40, freq="min", tz="UTC")
    )
    out = HourlyHorizontalDbDt(min_pairs=30).transform(gappy)
    assert out["n_pairs"].tolist() == [59.0, 19.0]
    assert np.isnan(out["dbh_dt_max_nT_min"].to_numpy()[1])


def test_fixture_storm_minute_dominates() -> None:
    minutes = IntermagnetReader().read([FIXTURE])
    out = HourlyHorizontalDbDt().transform(minutes)
    assert list(pd.DatetimeIndex(out.index)) == [
        to_utc("2024-05-10T22:00Z"),
        to_utc("2024-05-10T23:00Z"),
        to_utc("2024-05-11T00:00Z"),
    ]
    maxima = out["dbh_dt_max_nT_min"].to_numpy()
    assert maxima[1] > 250  # the 300 nT jump at 23:30
    assert maxima[0] < 20
    assert out["n_pairs"].tolist() == [59.0, 57.0, 29.0]  # fill minute at 23:10 removes 2 pairs
    assert np.isnan(maxima[2])  # only 30 minutes in the last hour -> 29 pairs < 30


def test_empty_input_gives_empty_hourly_frame() -> None:
    empty = _minutes([], [])
    out = HourlyHorizontalDbDt().transform(empty)
    assert out.empty
    assert list(out.columns) == ["dbh_dt_max_nT_min", "dbh_dt_mean_nT_min", "n_pairs"]
