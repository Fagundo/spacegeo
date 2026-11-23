"""Generic contract every concrete TabularEventModel must satisfy (auto-discovered)."""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import numpy as np
import pandas as pd
import pytest

import spacegeo
from spacegeo.common.exceptions import NotFittedError
from spacegeo.models.base import TabularEventModel


def _concrete() -> list[type[TabularEventModel]]:
    for info in pkgutil.walk_packages(spacegeo.__path__, prefix="spacegeo."):
        importlib.import_module(info.name)
    found: list[type[TabularEventModel]] = []
    stack: list[type[TabularEventModel]] = list(TabularEventModel.__subclasses__())
    while stack:
        cls = stack.pop()
        stack.extend(cls.__subclasses__())
        if not inspect.isabstract(cls):
            found.append(cls)
    return sorted(set(found), key=lambda c: c.__qualname__)


MODELS = _concrete()


def _table(n: int = 3000, seed: int = 0) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n)
    x2 = np.where(rng.uniform(size=n) < 0.2, np.nan, rng.normal(size=n))
    region = rng.choice(["a", "b", "c"], size=n)
    logit = -3 + 1.5 * x1 + (region == "a")
    y = rng.uniform(size=n) < 1 / (1 + np.exp(-logit))
    table = pd.DataFrame({"region": region, "x1": x1, "x2": x2})
    return table, pd.Series(y.astype(int), index=table.index)


def test_models_discovered() -> None:
    assert len(MODELS) >= 3


@pytest.mark.parametrize("model_cls", MODELS, ids=lambda c: c.__qualname__)
def test_probabilities_are_valid_and_deterministic(model_cls: type[TabularEventModel]) -> None:
    x, y = _table()
    first = model_cls.example().fit(x, y).predict_proba(x)
    second = model_cls.example().fit(x, y).predict_proba(x)
    assert first.shape == (len(x),)
    assert ((first > 0) & (first < 1)).all()
    np.testing.assert_allclose(first, second)


@pytest.mark.parametrize("model_cls", MODELS, ids=lambda c: c.__qualname__)
def test_calibrated_in_the_large(model_cls: type[TabularEventModel]) -> None:
    x, y = _table()
    p = model_cls.example().fit(x, y).predict_proba(x)
    assert p.mean() == pytest.approx(y.mean(), abs=0.02)


@pytest.mark.parametrize("model_cls", MODELS, ids=lambda c: c.__qualname__)
def test_requires_fit_and_aligned_targets(model_cls: type[TabularEventModel]) -> None:
    x, y = _table()
    with pytest.raises(NotFittedError):
        model_cls.example().predict_proba(x)
    with pytest.raises(ValueError, match="share an index"):
        model_cls.example().fit(x, y.iloc[:-1])
