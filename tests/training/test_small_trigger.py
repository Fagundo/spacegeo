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
from spacegeo.training.small_trigger import (
    SmallTriggerConfig,
    SmallTriggerExperiment,
    SmallTriggerReport,
)

REGIONS = {"box": GeoRegion((GeoBox(0, 6, 100, 106),))}
# Small events trigger as strongly per unit magnitude as large ones (alpha close
# to beta), so leaving them out should cost forecast skill.
TRUE = EtasParameters(mu=0.5, a=0.15, alpha=1.9, c=0.01, p=1.15, d=10.0, gamma=1.0, q=1.7)
SPAN = TimeWindow(to_utc("2000-01-01T00:00Z"), to_utc("2008-01-01T00:00Z"))


def _config() -> SmallTriggerConfig:
    return SmallTriggerConfig(
        experiment="small_trigger_etas",
        prereg=PreRegistration(
            hypothesis="h", comparison="c", metric="m", success="s", data="d", variants=1
        ),
        regions_file=Path("unused.yaml"),
        catalog=Path("unused"),
        mc=4.5,
        low_m0=3.0,
        train_start=to_utc("2000-01-01T00:00Z").to_pydatetime(),
        val_start=to_utc("2006-01-01T00:00Z").to_pydatetime(),
        val_end=to_utc("2008-01-01T00:00Z").to_pydatetime(),
        bootstrap_resamples=200,
    )


@pytest.fixture(scope="module")
def catalog() -> pd.DataFrame:
    settings = EtasSettings(m0=3.0)
    sim = EtasSimulator(REGIONS["box"], TRUE, np.log(10), settings).simulate(SPAN, seed=4)
    return sim.assign(event_id=[f"e{i}" for i in range(len(sim))])


def test_small_triggers_help_when_they_really_trigger(
    catalog: pd.DataFrame, tmp_path: Path
) -> None:
    result = SmallTriggerExperiment(_config(), REGIONS, catalog).run()
    row = result.per_region.to_dict("records")[0]
    assert 0 < float(row["fraction_above_mc"]) < 0.1
    assert result.pooled["info_gain_per_event"] > 0
    assert int(row["n_val"]) == int(result.weekly["n"].to_numpy().sum())

    run = RunDirectory(tmp_path, "small-test", GitState(commit="abc", dirty=False), seed=0)
    SmallTriggerReport().write(run, _config(), result)
    assert "Small quakes as ETAS triggers" in (run.path / "NOTES.md").read_text()


def test_low_m0_must_be_below_mc(catalog: pd.DataFrame) -> None:
    bad = _config().model_copy(update={"low_m0": 4.5})
    with pytest.raises(ValueError, match="low_m0"):
        SmallTriggerExperiment(bad, REGIONS, catalog)
