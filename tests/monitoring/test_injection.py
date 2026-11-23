import pandas as pd
import pytest

from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.models.base import ModelData
from spacegeo.models.count import PoissonCountModel
from spacegeo.monitoring.injection import InjectionStudy

FIT = TimeWindow(to_utc("2000-01-01T00:00Z"), to_utc("2000-03-11T00:00Z"))


def _model(per_week: int) -> PoissonCountModel:
    times = [FIT.start + duration(days=7 * w + 1) for w in range(10) for _ in range(per_week)]
    events = pd.DataFrame({"mag": 5.0}, index=pd.DatetimeIndex(times))
    return PoissonCountModel(duration(days=7)).fit(ModelData(events=events, window=FIT))


def _results(models: dict[str, PoissonCountModel], weeks: int = 4) -> pd.DataFrame:
    rows = []
    for w in range(weeks):
        for name, model in models.items():
            n = round(model.expected_count())
            rows.append(
                {
                    "window_start": FIT.end + duration(days=7 * w),
                    "region": name,
                    "observed": n,
                    "p_high": model.survival(n),
                    "p_low": model.cdf(n),
                }
            )
    return pd.DataFrame(rows)


def test_power_grows_with_burst_and_is_lower_in_busy_regions() -> None:
    models = {"quiet": _model(1), "busy": _model(30)}
    study = InjectionStudy(models, fdr=0.05, sizes=(1, 5, 20, 60))
    power = study.power(_results(models))["power"]
    assert power.loc[("quiet", 1)] == 0.0
    assert power.loc[("quiet", 20)] == 1.0
    assert power.loc[("busy", 5)] == 0.0
    assert power.loc[("busy", 60)] == 1.0
    smallest = InjectionStudy.minimum_detectable(study.power(_results(models)))
    assert smallest["quiet"] < smallest["busy"]


def test_sizes_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        InjectionStudy({}, sizes=(0,))
