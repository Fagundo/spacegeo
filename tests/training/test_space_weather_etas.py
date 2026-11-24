from pathlib import Path
from typing import ClassVar

import numpy as np
import pandas as pd
import pytest

from spacegeo.common.geo import GeoBox, GeoRegion
from spacegeo.common.run import GitState, RunDirectory
from spacegeo.common.time import TimeWindow, to_utc
from spacegeo.models.etas_parameters import EtasParameters, EtasSettings
from spacegeo.models.etas_simulation import EtasSimulator
from spacegeo.training.etas_baseline import PreRegistration
from spacegeo.training.space_weather_etas import (
    ExploratoryConfig,
    MechanismConfig,
    ShiftTestConfig,
    SpaceWeatherEtasConfig,
    SpaceWeatherEtasExperiment,
    SpaceWeatherSettings,
)
from spacegeo.training.space_weather_report import SpaceWeatherEtasReport

REGIONS = {
    "low_lat": GeoRegion((GeoBox(0, 8, 100, 108),)),
    "high_lat": GeoRegion((GeoBox(50, 58, 160, 168),)),
}
TRUE = EtasParameters(mu=0.3, a=0.25, alpha=1.6, c=0.02, p=1.15, d=40.0, gamma=1.0, q=1.7)
SPAN = TimeWindow(to_utc("2000-01-01T00:00Z"), to_utc("2005-01-01T00:00Z"))


class _QuickExperiment(SpaceWeatherEtasExperiment):
    BETA_RESAMPLES: ClassVar[int] = 3


def _config() -> SpaceWeatherEtasConfig:
    return SpaceWeatherEtasConfig(
        experiment="space_weather_etas",
        prereg=PreRegistration(
            hypothesis="h", comparison="c", metric="m", success="s", data="d", variants=5
        ),
        regions_file=Path("unused.yaml"),
        catalog=Path("unused"),
        train_start=to_utc("2000-01-01T00:00Z").to_pydatetime(),
        val_start=to_utc("2003-01-01T00:00Z").to_pydatetime(),
        val_end=to_utc("2004-07-01T00:00Z").to_pydatetime(),
        bootstrap_block_weeks=4,
        bootstrap_resamples=100,
        space_weather=SpaceWeatherSettings(
            archive=Path("unused"),
            mechanisms=(
                MechanismConfig(name="compression", feature="dynamic_pressure"),
                MechanismConfig(name="variability", feature="bz_sigma"),
            ),
            taus_days=(1.0, 4.0),
            detrend_days=60.0,
            shift_test=ShiftTestConfig(shifts=19, min_offset_days=60.0),
            exploratory=ExploratoryConfig(joint_model=True, extra_tau_days=16.0),
        ),
    )


@pytest.fixture(scope="module")
def catalog() -> pd.DataFrame:
    frames = [
        EtasSimulator(region, TRUE, np.log(10), EtasSettings()).simulate(SPAN, seed=i)
        for i, region in enumerate(REGIONS.values())
    ]
    return pd.concat(frames).sort_index()


@pytest.fixture(scope="module")
def omni() -> pd.DataFrame:
    index = pd.date_range(SPAN.start, SPAN.end, freq="h", inclusive="left")
    rng = np.random.default_rng(3)
    smooth = np.convolve(rng.normal(size=len(index) + 23), np.ones(24) / 5, mode="valid")
    frame = pd.DataFrame(
        {"pdyn_nPa": np.exp(smooth), "sigma_bz_nT": np.exp(rng.normal(size=len(index)))},
        index=index,
    )
    frame.iloc[5000:5400] = np.nan  # a data gap
    return frame


def test_null_run_reports_without_detection(
    catalog: pd.DataFrame, omni: pd.DataFrame, tmp_path: Path
) -> None:
    result = _QuickExperiment(_config(), REGIONS, catalog, omni).run()
    table = result.variants
    assert list(table.index) == [
        "compression",
        "variability",
        "joint",
        "compression+16d",
        "variability+16d",
    ]
    assert table["primary"].tolist() == [True, True, False, False, False]
    assert (
        not table["detected"].to_numpy(dtype=bool).any()
    )  # space weather is unrelated to the simulated quakes
    assert table["p_shift"].iloc[:2].between(0.05, 1).all()
    assert table["p_shift"].iloc[2:].isna().all()
    assert set(result.shift_null) == {"compression", "variability"}
    assert len(result.shift_null["compression"]) == 19
    maglat = result.per_region["geomagnetic_lat_deg"].to_numpy(dtype=np.float64)
    assert maglat[list(REGIONS).index("high_lat")] > 40
    assert result.weekly["n"].to_numpy().sum() == result.per_region["n_val"].to_numpy().sum() * 5

    run = RunDirectory(tmp_path, "sw-test", GitState(commit="abc", dirty=False), seed=0)
    SpaceWeatherEtasReport().write(run, _config(), result)
    names = {p.name for p in run.path.iterdir()}
    assert {"metrics.json", "NOTES.md", "variants.csv", "response_by_scale.png"} <= names
    assert "No mechanism detected (null)" in (run.path / "NOTES.md").read_text()


def test_validation_end_bounds_every_input(catalog: pd.DataFrame, omni: pd.DataFrame) -> None:
    experiment = _QuickExperiment(_config(), REGIONS, catalog, omni)
    end = _config().validation.end
    assert experiment._catalog.index.max() < end
    assert experiment._covariates._data.index.max() < end
