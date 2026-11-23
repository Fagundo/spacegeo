"""Generic contract every concrete CountModel must satisfy.

New count models are discovered automatically.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from itertools import pairwise

import numpy as np
import pandas as pd
import pytest

import spacegeo
from spacegeo.common.time import TimeWindow, to_utc
from spacegeo.models.base import CountModel, ModelData


def _concrete() -> list[type[CountModel]]:
    for info in pkgutil.walk_packages(spacegeo.__path__, prefix="spacegeo."):
        importlib.import_module(info.name)
    found: list[type[CountModel]] = []
    stack: list[type[CountModel]] = list(CountModel.__subclasses__())
    while stack:
        cls = stack.pop()
        stack.extend(cls.__subclasses__())
        if not inspect.isabstract(cls):
            found.append(cls)
    return sorted(set(found), key=lambda c: c.__qualname__)


MODELS = _concrete()
WINDOW = TimeWindow(to_utc("2000-01-01T00:00Z"), to_utc("2010-01-01T00:00Z"))


def _data(seed: int = 0, clustered: bool = True) -> ModelData:
    rng = np.random.default_rng(seed)
    span = (WINDOW.end - WINDOW.start).total_seconds()
    offsets = rng.uniform(0, span, size=800)
    if clustered:
        bursts = rng.choice(offsets, size=20)
        offsets = np.concatenate([offsets, np.repeat(bursts, 15) + rng.uniform(0, 3e5, 300)])
    times = pd.DatetimeIndex(WINDOW.start + pd.to_timedelta(np.sort(offsets), unit="s"))
    events = pd.DataFrame({"mag": 5.0}, index=times[times < WINDOW.end])
    return ModelData(events=events, window=WINDOW)


def test_count_models_discovered() -> None:
    assert len(MODELS) >= 2


@pytest.mark.parametrize("model_cls", MODELS, ids=lambda c: c.__qualname__)
def test_pmf_is_a_distribution(model_cls: type[CountModel]) -> None:
    model = model_cls.example().fit(_data())
    pmf = model.pmf(np.arange(5000))
    assert (pmf >= 0).all()
    assert pmf.sum() == pytest.approx(1.0, abs=1e-9)
    mean = float((np.arange(5000) * pmf).sum())
    assert mean == pytest.approx(model.expected_count(), rel=1e-6)


@pytest.mark.parametrize("model_cls", MODELS, ids=lambda c: c.__qualname__)
def test_tails_are_consistent(model_cls: type[CountModel]) -> None:
    model = model_cls.example().fit(_data())
    assert model.survival(0) == 1.0
    assert model.cdf(-1) == 0.0
    sv = [model.survival(n) for n in range(0, 60)]
    assert all(a >= b for a, b in pairwise(sv))
    for n in (1, 5, 20, 40):
        assert model.survival(n) + model.cdf(n - 1) == pytest.approx(1.0, abs=1e-9)
    assert 0.0 <= model.survival(10_000) < 1e-12


@pytest.mark.parametrize("model_cls", MODELS, ids=lambda c: c.__qualname__)
def test_expected_count_scales_with_rate(model_cls: type[CountModel]) -> None:
    data = _data(clustered=False)
    model = model_cls.example().fit(data)
    weeks = WINDOW.duration / model.horizon
    assert model.expected_count() == pytest.approx(data.n_events / weeks, rel=0.02)


@pytest.mark.parametrize("model_cls", MODELS, ids=lambda c: c.__qualname__)
def test_empty_history_gives_zero_rate(model_cls: type[CountModel]) -> None:
    empty = ModelData(
        events=pd.DataFrame({"mag": []}, index=pd.DatetimeIndex([], tz="UTC")), window=WINDOW
    )
    model = model_cls.example().fit(empty)
    assert model.expected_count() == 0.0
    assert model.survival(1) == 0.0
