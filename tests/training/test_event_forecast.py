from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from spacegeo.common.geo import GeoBox, GeoRegion
from spacegeo.common.run import GitState, RunDirectory
from spacegeo.common.time import TimeWindow, to_utc
from spacegeo.models.etas_parameters import EtasParameters, EtasSettings
from spacegeo.models.etas_simulation import EtasSimulator
from spacegeo.training.etas_baseline import PreRegistration
from spacegeo.training.event_forecast import (
    REFERENCE,
    EventForecastConfig,
    EventForecastExperiment,
)
from spacegeo.training.event_forecast_report import EventForecastReport

REGIONS = {
    "west": GeoRegion((GeoBox(0, 8, 100, 108),)),
    "east": GeoRegion((GeoBox(0, 8, 120, 128),)),
}
TRUE = EtasParameters(mu=0.08, a=0.2, alpha=1.8, c=0.02, p=1.15, d=40.0, gamma=1.0, q=1.7)
"""Strongly clustered (branching ratio ~0.9), so ETAS carries real information."""
SPAN = TimeWindow(to_utc("2000-01-01T00:00Z"), to_utc("2012-01-01T00:00Z"))


def _config() -> EventForecastConfig:
    return EventForecastConfig(
        experiment="event_forecast",
        prereg=PreRegistration(
            hypothesis="h", comparison="c", metric="m", success="s", data="d", variants=1
        ),
        regions_file="unused.yaml",
        catalog="unused",
        target_magnitude=5.0,
        secondary_target_magnitude=5.5,
        history_start=to_utc("2000-01-01T00:00Z").to_pydatetime(),
        train_start=to_utc("2001-01-01T00:00Z").to_pydatetime(),
        val_start=to_utc("2009-01-01T00:00Z").to_pydatetime(),
        val_end=to_utc("2011-01-01T00:00Z").to_pydatetime(),
        bootstrap_resamples=200,
    )


@pytest.fixture(scope="module")
def catalog() -> pd.DataFrame:
    frames = [
        EtasSimulator(region, TRUE, np.log(10), EtasSettings()).simulate(SPAN, seed=10 + i)
        for i, region in enumerate(REGIONS.values())
    ]
    frame = pd.concat(frames).sort_index()
    return frame.assign(depth_km=10.0)


def test_experiment_runs_scores_and_reports(catalog: pd.DataFrame, tmp_path: Path) -> None:
    result = EventForecastExperiment(_config(), REGIONS, catalog).run()
    scores = result.scores.set_index(["target", "model"])
    assert set(scores.index.get_level_values("model")) == {
        "climatology",
        "etas_raw",
        REFERENCE,
        "gradient_boosting",
    }
    assert np.isfinite(scores["mean_log_score"]).all()
    assert scores.loc[("y_primary", REFERENCE), f"gain_vs_{REFERENCE}"] == pytest.approx(0.0)
    # ETAS carries real information on a clustered ETAS-generated catalog.
    gain_lo = scores.loc[[("y_primary", REFERENCE)], "gain_vs_climatology_lo"].to_numpy()
    assert gain_lo[0] > 0
    assert (
        result.predictions["week"].min()
        >= _config().weeks(_config().val_start, _config().val_end)[0].start
    )
    assert not result.importance.empty

    run = RunDirectory(tmp_path, "gbm-test", GitState(commit="abc", dirty=False), seed=0)
    EventForecastReport().write(run, _config(), result)
    names = {p.name for p in run.path.iterdir()}
    assert {
        "metrics.json",
        "NOTES.md",
        "scores.csv",
        "reliability.png",
        "gain_by_model.png",
    } <= names


def test_test_span_is_never_read(catalog: pd.DataFrame) -> None:
    experiment = EventForecastExperiment(_config(), REGIONS, catalog)
    assert experiment._catalog.index.max() < to_utc("2011-01-01T00:00Z")
