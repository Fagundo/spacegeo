from pathlib import Path

import numpy as np
import pandas as pd

from spacegeo.common.geo import GeoBox, GeoRegion
from spacegeo.common.run import GitState, RunDirectory
from spacegeo.common.time import duration, to_utc
from spacegeo.training.anomaly_followup import (
    AnomalyFollowupConfig,
    AnomalyFollowupExperiment,
    AnomalyFollowupReport,
)
from spacegeo.training.etas_baseline import PreRegistration

REGIONS = {
    "a": GeoRegion((GeoBox(0, 10, 0, 10),)),
    "b": GeoRegion((GeoBox(20, 30, 0, 10),)),
}
VAL_START = to_utc("2020-01-06T00:00Z")


def _config(flags: Path) -> AnomalyFollowupConfig:
    return AnomalyFollowupConfig(
        experiment="anomaly_followup",
        prereg=PreRegistration(
            hypothesis="h", comparison="c", metric="m", success="s", data="d", variants=1
        ),
        regions_file=Path("unused.yaml"),
        catalog=Path("unused"),
        flags_file=flags,
        train_start=to_utc("2018-01-01T00:00Z").to_pydatetime(),
        val_start=to_utc("2020-01-01T00:00Z").to_pydatetime(),
        val_end=to_utc("2022-01-01T00:00Z").to_pydatetime(),
        bootstrap_resamples=300,
    )


def _week(i: int) -> pd.Timestamp:
    return VAL_START + duration(days=7 * i)


def _setup(tmp_path: Path) -> tuple[AnomalyFollowupConfig, pd.DataFrame]:
    weeks = [_week(i) for i in range(100)]
    flagged = {(10, "a"), (30, "a"), (50, "b"), (70, "b"), (80, "a")}
    rows = [
        {
            "test": test,
            "window_start": w,
            "region": r,
            "flag": "excess" if (i, r) in flagged else "",
        }
        for test in ("activity", "mainshocks")
        for i, w in enumerate(weeks)
        for r in REGIONS
    ]
    rows[0]["flag"] = "deficit"
    path = tmp_path / "flags.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    quakes = [
        (_week(11) + duration(days=3), 5.0, 7.2),  # 10 days after flagged week 10 ends: hit
        (_week(31) + duration(days=20), 5.0, 7.5),  # after flagged week 30: hit
        (_week(50) + duration(days=2), 25.0, 7.1),  # inside flagged week 50: does not count
        (_week(60), 9.5, 7.0),  # unflagged period, ~500 km from the M7.5 (not its aftershock)
        (_week(60) + duration(days=1), 5.1, 6.0),  # smaller, ignored
    ]
    lon = [9.5 if q[1] == 9.5 else 5.0 for q in quakes]
    catalog = pd.DataFrame(
        {"lat_deg": [q[1] for q in quakes], "lon_deg": lon, "mag": [q[2] for q in quakes]},
        index=pd.DatetimeIndex([q[0] for q in quakes]),
    ).sort_index()
    return _config(path), catalog


def test_relative_risk_and_report(tmp_path: Path) -> None:
    config, catalog = _setup(tmp_path)
    result = AnomalyFollowupExperiment(config, REGIONS, catalog).run()
    rows = {str(r["comparison"]): r for r in result.comparisons.to_dict("records")}
    primary = rows["mainshocks_excess_30d"]
    assert int(primary["flagged_weeks"]) == 5
    assert int(primary["flagged_with_target"]) == 2
    assert float(primary["relative_risk"]) > 5
    assert int(rows["any_deficit_30d"]["flagged_weeks"]) == 1
    assert len(result.targets) == 4
    assert set(result.base_rates["span"]) == {"train", "validation"}

    run = RunDirectory(tmp_path / "runs", "followup-test", GitState("abc", dirty=False), seed=0)
    AnomalyFollowupReport().write(run, config, result)
    assert "Do anomaly flags precede" in (run.path / "NOTES.md").read_text()


def test_horizon_never_reaches_past_validation(tmp_path: Path) -> None:
    config, catalog = _setup(tmp_path)
    experiment = AnomalyFollowupExperiment(config, REGIONS, catalog)
    flags = experiment._flags()
    cmp = experiment.comparisons()[3]  # 60-day horizon
    units = experiment._units(flags, cmp)
    last_end = units["window_start"].max() + duration(days=7 + cmp.horizon_days)
    assert last_end <= to_utc("2022-01-01T00:00Z")
    assert np.isfinite(experiment.run().comparisons["p_rr_le_1"]).all()
