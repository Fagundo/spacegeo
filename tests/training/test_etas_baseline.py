from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from spacegeo.common.geo import GeoBox, GeoRegion
from spacegeo.common.run import GitState, RunDirectory
from spacegeo.common.time import TimeWindow, to_utc
from spacegeo.models.etas_parameters import EtasParameters, EtasSettings
from spacegeo.models.etas_simulation import EtasSimulator
from spacegeo.training.etas_baseline import (
    EtasBaselineExperiment,
    EtasExperimentConfig,
    PreRegistration,
)
from spacegeo.training.etas_report import EtasBaselineReport

REGIONS = {
    "west": GeoRegion((GeoBox(0, 8, 100, 108),)),
    "east": GeoRegion((GeoBox(0, 8, 120, 128),)),
}
TRUE = EtasParameters(mu=0.2, a=0.25, alpha=1.6, c=0.02, p=1.15, d=40.0, gamma=1.0, q=1.7)
SPAN = TimeWindow(to_utc("2000-01-01T00:00Z"), to_utc("2012-01-01T00:00Z"))


def _config() -> EtasExperimentConfig:
    return EtasExperimentConfig(
        experiment="etas_baseline",
        prereg=PreRegistration(
            hypothesis="h", comparison="c", metric="m", success="s", data="d", variants=1
        ),
        regions_file=Path("unused.yaml"),
        catalog=Path("unused"),
        train_start=to_utc("2000-01-01T00:00Z").to_pydatetime(),
        val_start=to_utc("2009-01-01T00:00Z").to_pydatetime(),
        val_end=to_utc("2011-01-01T00:00Z").to_pydatetime(),
        bootstrap_resamples=200,
    )


@pytest.fixture(scope="module")
def catalog() -> pd.DataFrame:
    frames = [
        EtasSimulator(region, TRUE, np.log(10), EtasSettings()).simulate(SPAN, seed=i)
        for i, region in enumerate(REGIONS.values())
    ]
    return pd.concat(frames).sort_index()


def test_experiment_scores_and_reports(catalog: pd.DataFrame, tmp_path: Path) -> None:
    result = EtasBaselineExperiment(_config(), REGIONS, catalog).run()
    pooled = result.pooled
    assert pooled["info_gain_lo"] > 0
    assert pooled["info_gain_lo"] <= pooled["info_gain_per_event"] <= pooled["info_gain_hi"]
    assert set(result.per_region.index) == set(REGIONS)
    assert (result.per_region["branching_ratio"] > 0).all()
    assert result.weekly["week"].min() >= _config().validation.start
    assert result.weekly["week"].max() < _config().validation.end
    assert int(result.weekly["n"].sum()) == int(result.per_region["n_val"].sum())

    run = RunDirectory(tmp_path, "etas-test", GitState(commit="abc", dirty=False), seed=0)
    EtasBaselineReport().write(run, _config(), result)
    names = {p.name for p in run.path.iterdir()}
    assert {"metrics.json", "NOTES.md", "per_region.csv", "info_gain_by_region.png"} <= names
    assert "Primary criterion MET" in (run.path / "NOTES.md").read_text()


def test_test_span_is_never_read(catalog: pd.DataFrame) -> None:
    experiment = EtasBaselineExperiment(_config(), REGIONS, catalog)
    assert experiment._catalog.index.max() < _config().validation.end
