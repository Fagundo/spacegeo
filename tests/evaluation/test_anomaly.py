import numpy as np
import pandas as pd
import pytest

from spacegeo.common.exceptions import NotFittedError
from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.evaluation.anomaly import BoxConfig, RegionalAnomalyScanner, RegionConfig
from spacegeo.models.count import PoissonCountModel

BASELINE = TimeWindow(to_utc("2000-01-01T00:00Z"), to_utc("2020-01-01T00:00Z"))
OBS = TimeWindow(to_utc("2026-11-16T00:00Z"), to_utc("2026-11-23T00:00Z"))
REGIONS = [
    RegionConfig(
        name=f"r{i}",
        boxes=(
            BoxConfig(lat_min_deg=10 * i, lat_max_deg=10 * i + 5, lon_min_deg=0, lon_max_deg=5),
        ),
    )
    for i in range(5)
] + [
    RegionConfig(
        name="dateline",
        boxes=(BoxConfig(lat_min_deg=-30, lat_max_deg=-20, lon_min_deg=175, lon_max_deg=-175),),
    )
]


def _events(rng: np.random.Generator, burst_region: int, burst: int) -> pd.DataFrame:
    rows = []
    span = (BASELINE.end - BASELINE.start).total_seconds()
    weeks = BASELINE.duration / duration(days=7)
    for i, region in enumerate(REGIONS[:5]):
        n_hist = rng.poisson(2.0 * weeks)
        t = BASELINE.start + pd.to_timedelta(rng.uniform(0, span, n_hist), unit="s")
        rows.append(
            pd.DataFrame(
                {"lat_deg": region.boxes[0].lat_min_deg + 1, "lon_deg": 1.0, "mag": 4.8}, index=t
            )
        )
        n_obs = burst if i == burst_region else 2
        t_obs = OBS.start + pd.to_timedelta(rng.uniform(0, 6 * 86400, n_obs), unit="s")
        rows.append(
            pd.DataFrame(
                {"lat_deg": region.boxes[0].lat_min_deg + 1, "lon_deg": 1.0, "mag": 5.0},
                index=t_obs,
            )
        )
    dateline = pd.DataFrame(
        {"lat_deg": -25.0, "lon_deg": [179.5, -179.5], "mag": 5.0},
        index=pd.DatetimeIndex([OBS.start + duration(days=1), OBS.start + duration(days=2)]),
    )
    return pd.concat([*rows, dateline]).sort_index()


def _scanner() -> RegionalAnomalyScanner:
    return RegionalAnomalyScanner(REGIONS, lambda: PoissonCountModel(duration(days=7)), fdr=0.05)


def test_burst_region_is_flagged_and_others_are_not() -> None:
    table = _scanner().scan(
        _events(np.random.default_rng(1), burst_region=3, burst=14), BASELINE, OBS
    )
    table = table.drop(index="dateline")  # no history there, so trivially anomalous
    assert table.index[0] == "r3"
    assert table.loc["r3", "flag"] == "excess"
    assert table.loc["r3", "observed"] == 14
    assert (table.drop(index="r3")["flag"] == "").all()
    assert table.loc["r0", "expected"] == pytest.approx(2.0, rel=0.05)


def test_dateline_region_counts_both_sides() -> None:
    table = _scanner().scan(
        _events(np.random.default_rng(2), burst_region=0, burst=2), BASELINE, OBS
    )
    assert table.loc["dateline", "observed"] == 2
    assert table.loc["dateline", "expected"] == 0.0
    assert table.loc["dateline", "p_high"] == 0.0


def test_window_checks() -> None:
    events = _events(np.random.default_rng(3), 0, 2)
    with pytest.raises(ValueError, match="horizon"):
        _scanner().scan(events, BASELINE, TimeWindow(OBS.start, OBS.end + duration(days=1)))
    overlapping = TimeWindow(BASELINE.start, OBS.start + duration(days=1))
    with pytest.raises(ValueError, match="after the fit window"):
        _scanner().scan(events, overlapping, OBS)


def test_score_many_windows_matches_single_scans() -> None:
    events = _events(np.random.default_rng(4), burst_region=2, burst=12)
    scanner = _scanner().fit(events, BASELINE)
    earlier = TimeWindow(OBS.start - duration(days=7), OBS.start)
    long = scanner.score(events, [earlier, OBS])
    assert list(long["window_start"].unique()) == [earlier.start, OBS.start]
    single = _scanner().scan(events, BASELINE, OBS)
    latest = long.loc[long["window_start"] == OBS.start].set_index("region")
    pd.testing.assert_series_equal(latest["p_high"].sort_index(), single["p_high"].sort_index())
    assert (long.loc[long["window_start"] == earlier.start, "observed"] == 0).all()


def test_non_nanosecond_index_is_handled() -> None:
    events = _events(np.random.default_rng(5), burst_region=1, burst=9)
    events.index = pd.DatetimeIndex(events.index).as_unit("us")
    table = _scanner().scan(events, BASELINE, OBS)
    assert table.loc["r1", "observed"] == 9


def test_score_requires_fit() -> None:
    with pytest.raises(NotFittedError):
        _scanner().score(pd.DataFrame(), [OBS])
