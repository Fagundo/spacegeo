from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.evaluation.anomaly import BoxConfig, RegionConfig
from spacegeo.monitoring.calibration import CalibrationSummary
from spacegeo.monitoring.config import WeeklyScanConfig
from spacegeo.monitoring.report import ScanReportWriter
from spacegeo.monitoring.validation import ValidationSuite
from spacegeo.monitoring.weekly_scan import WeeklyAnomalyScan

REGIONS = tuple(
    RegionConfig(
        name=f"r{i}",
        boxes=(
            BoxConfig(lat_min_deg=10 * i, lat_max_deg=10 * i + 5, lon_min_deg=0, lon_max_deg=5),
        ),
        mc=4.5,
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
        lat = rng.uniform(region.boxes[0].lat_min_deg, region.boxes[0].lat_max_deg, n)
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
    results = WeeklyAnomalyScan(CONFIG, _null_catalog()).validate().results
    assert set(results["test"]) == {"activity", "mainshocks"}
    assert results["window_start"].min() >= CONFIG.validation.start + CONFIG.gap
    assert results["window_start"].max() < CONFIG.validation.end
    summary = CalibrationSummary().by_test(results)
    assert bool(summary["calibrated"].all())
    assert summary.loc["activity", "observed_over_expected"] == pytest.approx(1.0, abs=0.05)
    assert summary["pit_max_bin_deviation"].to_numpy().max() < 0.03  # PIT ~ uniform


def test_validation_suite_outputs(tmp_path: Path) -> None:
    scan = WeeklyAnomalyScan(CONFIG, _null_catalog())
    report = ValidationSuite(CONFIG, scan, sizes=(1, 10, 30)).run()

    comparison = report.model_comparison
    assert comparison.loc[("activity", "poisson"), "info_gain"] == pytest.approx(0.0)
    # On Poisson data no model should beat Poisson by a meaningful margin.
    assert comparison["info_gain"].to_numpy().max() < 0.02

    power = report.power.set_index(["test", "region", "added"])["power"]
    for test in ("activity", "mainshocks"):
        assert power.loc[(test, "r0", 30)] > power.loc[(test, "r0", 1)]
        assert power.loc[(test, "r0", 30)] > 0.95
        assert power.loc[(test, "r0", 1)] < 0.05

    writer = ScanReportWriter(tmp_path)
    writer.write_validation(report)
    out = tmp_path / "validation"
    for name in ("pit.png", "power.png", "README.md", "model_comparison.csv", "power.csv"):
        assert (out / name).exists(), name
    first = (out / "pit.png").read_bytes(), (out / "weekly.csv.gz").read_bytes()
    writer.write_validation(report)
    assert ((out / "pit.png").read_bytes(), (out / "weekly.csv.gz").read_bytes()) == first


def test_predict_scores_test_weeks_and_report_writes(tmp_path: Path) -> None:
    catalog = _null_catalog()
    burst_t = to_utc("2018-02-20T00:00Z") + pd.to_timedelta(np.arange(25) * 3600, unit="s")
    burst = pd.DataFrame(
        {"lat_deg": 32.0, "lon_deg": 2.0, "mag": 4.6}, index=pd.DatetimeIndex(burst_t)
    )
    catalog = pd.concat([catalog, burst]).sort_index()
    scan = WeeklyAnomalyScan(CONFIG, catalog)
    results = scan.predict(AS_OF).results
    assert results["window_start"].min() >= CONFIG.refit.end + CONFIG.gap
    latest = results.loc[
        (results["window_start"] == results["window_start"].max()) & (results["test"] == "activity")
    ]
    assert latest.set_index("region").loc["r3", "flag"] == "excess"

    calibration = CalibrationSummary().by_test(scan.validate().results)
    ScanReportWriter(tmp_path).write_predictions(results, calibration)
    text = (tmp_path / "test" / "latest.md").read_text()
    assert "## activity" in text
    assert "r3" in text
    assert "calibrated" in text


def test_split_must_be_ordered() -> None:
    with pytest.raises(ValueError, match="train_start < val_start"):
        WeeklyScanConfig(
            regions=REGIONS,
            train_start=CONFIG.val_start,
            val_start=CONFIG.train_start,
            test_start=CONFIG.test_start,
        )


def test_gap_must_cover_horizon() -> None:
    with pytest.raises(ValueError, match="gap_days"):
        WeeklyScanConfig(
            regions=REGIONS,
            train_start=CONFIG.train_start,
            val_start=CONFIG.val_start,
            test_start=CONFIG.test_start,
            gap_days=3,
        )


def test_committed_config_loads_with_disjoint_regions() -> None:
    cfg = WeeklyScanConfig.from_yaml(
        Path(__file__).parents[2] / "configs" / "ring_of_fire_scan.yaml"
    )
    assert len(cfg.regions) == 17
    assert cfg.catalog_min_magnitude == 2.5


def test_overlapping_regions_rejected() -> None:
    overlapping = (
        RegionConfig(
            name="a",
            boxes=(BoxConfig(lat_min_deg=0, lat_max_deg=10, lon_min_deg=0, lon_max_deg=10),),
        ),
        RegionConfig(
            name="b",
            boxes=(BoxConfig(lat_min_deg=5, lat_max_deg=15, lon_min_deg=5, lon_max_deg=15),),
        ),
    )
    with pytest.raises(ValueError, match="overlap: a/b"):
        WeeklyScanConfig(
            regions=overlapping,
            train_start=CONFIG.train_start,
            val_start=CONFIG.val_start,
            test_start=CONFIG.test_start,
        )


def test_mc_is_fitted_per_region_on_training_only() -> None:
    estimated = tuple(r.model_copy(update={"mc": None}) for r in REGIONS)
    cfg = CONFIG.model_copy(update={"regions": estimated})
    catalog = _null_catalog()
    late = catalog.index >= CONFIG.val_start
    catalog.loc[late, "mag"] = catalog.loc[late, "mag"] - 1.0  # later data must not move Mc
    scan = WeeklyAnomalyScan(cfg, catalog)
    assert set(scan.mc) == {r.name for r in REGIONS}
    assert all(4.5 <= v <= 4.9 for v in scan.mc.values())
