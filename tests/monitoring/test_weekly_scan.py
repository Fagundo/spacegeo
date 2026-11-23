from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.evaluation.anomaly import RegionConfig
from spacegeo.monitoring.calibration import CalibrationSummary
from spacegeo.monitoring.config import WeeklyScanConfig
from spacegeo.monitoring.report import ScanReportWriter
from spacegeo.monitoring.weekly_scan import WeeklyAnomalyScan

REGIONS = tuple(
    RegionConfig(
        name=f"r{i}", lat_min_deg=10 * i, lat_max_deg=10 * i + 5, lon_min_deg=0, lon_max_deg=5
    )
    for i in range(6)
)
CONFIG = WeeklyScanConfig(
    regions=REGIONS,
    train_start=to_utc("2010-01-01T00:00Z").to_pydatetime(),
    val_start=to_utc("2016-01-01T00:00Z").to_pydatetime(),
    test_start=to_utc("2018-01-01T00:00Z").to_pydatetime(),
)
AS_OF = to_utc("2018-03-01T00:00Z")


def _null_catalog(seed: int = 0) -> pd.DataFrame:
    """Independent Poisson events, ~3/week per region, far apart (no declustering)."""
    rng = np.random.default_rng(seed)
    start, end = CONFIG.train.start, AS_OF
    weeks = (end - start) / duration(days=7)
    frames = []
    for region in REGIONS:
        n = rng.poisson(3 * weeks)
        t = start + pd.to_timedelta(rng.uniform(0, (end - start).total_seconds(), n), unit="s")
        lat = rng.uniform(region.lat_min_deg, region.lat_max_deg, n)
        lon = rng.uniform(0, 5, n)
        frames.append(
            pd.DataFrame(
                {"lat_deg": lat, "lon_deg": lon, "mag": 4.5 + rng.exponential(0.2, n)}, index=t
            )
        )
    return pd.concat(frames).sort_index()


def test_weeks_are_anchored_and_complete() -> None:
    scan = WeeklyAnomalyScan(CONFIG, _null_catalog())
    weeks = scan.weeks(TimeWindow(to_utc("2018-01-01T00:00Z"), to_utc("2018-01-30T00:00Z")))
    assert [w.start.day_name() for w in weeks] == ["Monday"] * 4
    assert weeks[-1].end <= to_utc("2018-01-30T00:00Z")


def test_validation_is_calibrated_on_null_data() -> None:
    results = WeeklyAnomalyScan(CONFIG, _null_catalog()).validate()
    assert set(results["test"]) == {"activity", "mainshocks"}
    assert results["window_start"].min() >= CONFIG.validation.start
    assert results["window_start"].max() < CONFIG.validation.end
    summary = CalibrationSummary().by_test(results)
    assert bool(summary["calibrated"].all())
    assert summary.loc["activity", "observed_over_expected"] == pytest.approx(1.0, abs=0.05)


def test_predict_scores_test_weeks_and_report_writes(tmp_path: Path) -> None:
    catalog = _null_catalog()
    burst_t = to_utc("2018-02-20T00:00Z") + pd.to_timedelta(np.arange(25) * 3600, unit="s")
    burst = pd.DataFrame(
        {"lat_deg": 32.0, "lon_deg": 2.0, "mag": 4.6}, index=pd.DatetimeIndex(burst_t)
    )
    catalog = pd.concat([catalog, burst]).sort_index()
    scan = WeeklyAnomalyScan(CONFIG, catalog)
    results = scan.predict(AS_OF)
    assert results["window_start"].min() >= CONFIG.refit.end
    latest = results.loc[
        (results["window_start"] == results["window_start"].max()) & (results["test"] == "activity")
    ]
    assert latest.set_index("region").loc["r3", "flag"] == "excess"

    validation = scan.validate()
    writer = ScanReportWriter(tmp_path)
    calibration = CalibrationSummary().by_test(validation)
    writer.write_validation(validation, calibration, CalibrationSummary.by_region(validation))
    writer.write_predictions(results, calibration)
    text = (tmp_path / "test" / "latest.md").read_text()
    assert "## activity" in text
    assert "r3" in text
    assert "calibrated" in text
    first = (tmp_path / "validation" / "weekly.csv.gz").read_bytes()
    writer.write_validation(validation, calibration, CalibrationSummary.by_region(validation))
    assert (tmp_path / "validation" / "weekly.csv.gz").read_bytes() == first


def test_split_must_be_ordered() -> None:
    with pytest.raises(ValueError, match="train_start < val_start"):
        WeeklyScanConfig(
            regions=REGIONS,
            train_start=CONFIG.val_start,
            val_start=CONFIG.train_start,
            test_start=CONFIG.test_start,
        )
