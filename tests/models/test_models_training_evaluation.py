import numpy as np
import pandas as pd
import pytest

from spacegeo.common.exceptions import NotFittedError
from spacegeo.common.time import ZERO, TimeWindow, duration, to_utc
from spacegeo.evaluation.base import Evaluator
from spacegeo.evaluation.metrics import InformationGain, LogLikelihood
from spacegeo.models.base import ForecastModel, ModelData
from spacegeo.training.base import TemporalSplitter, Trainer


class _PoissonRate(ForecastModel):
    """Homogeneous Poisson process: rate = events per day in the fit window."""

    def __init__(self, rate_per_day: float | None = None) -> None:
        self._rate = rate_per_day or 0.0
        self._fixed = rate_per_day is not None

    def _fit(self, data: ModelData) -> None:
        if not self._fixed:
            self._rate = data.n_events / (data.window.duration / duration(days=1))

    def _log_likelihood(self, data: ModelData) -> float:
        days = data.window.duration / duration(days=1)
        return data.n_events * np.log(self._rate) - self._rate * days


SPAN = TimeWindow(to_utc("2000-01-01T00:00Z"), to_utc("2010-01-01T00:00Z"))
EVENTS = pd.DataFrame(
    {"mag": 6.0},
    index=pd.date_range(SPAN.start, SPAN.end, freq="7D", inclusive="left"),
)
DATA = ModelData(events=EVENTS, window=SPAN)


def test_splitter_enforces_gap_and_order() -> None:
    split = TemporalSplitter(gap=duration(days=30)).split(
        SPAN, "2006-01-01T00:00Z", "2008-01-01T00:00Z"
    )
    assert split.validation.start - split.train.end == duration(days=30)
    assert split.test.start - split.validation.end == duration(days=30)
    with pytest.raises(ValueError, match="ordered"):
        TemporalSplitter(gap=ZERO).split(SPAN, "2008-01-01T00:00Z", "2006-01-01T00:00Z")
    with pytest.raises(ValueError, match="ordered"):  # gap swallows the whole validation span
        TemporalSplitter(gap=duration(days=800)).split(
            SPAN, "2006-01-01T00:00Z", "2008-01-01T00:00Z"
        )
    no_gap = TemporalSplitter(gap=ZERO).split(SPAN, "2006-01-01T00:00Z", "2008-01-01T00:00Z")
    assert no_gap.train.end == no_gap.validation.start


def test_model_requires_fit() -> None:
    with pytest.raises(NotFittedError):
        _PoissonRate().log_likelihood(DATA)


def test_information_gain_prefers_correct_rate() -> None:
    split = TemporalSplitter(gap=duration(days=30)).split(
        SPAN, "2006-01-01T00:00Z", "2008-01-01T00:00Z"
    )
    model = Trainer().train(_PoissonRate(), DATA, split)
    baseline = Trainer().train(_PoissonRate(rate_per_day=1.0), DATA, split)
    results = Evaluator(
        metrics=[LogLikelihood()], comparative=[InformationGain()], baseline=baseline
    ).evaluate(model, DATA.restrict(split.validation))
    assert results["information_gain"] > 0
    assert "log_likelihood" in results


def test_evaluator_needs_baseline_for_comparative() -> None:
    with pytest.raises(ValueError, match="baseline"):
        Evaluator(comparative=[InformationGain()])
