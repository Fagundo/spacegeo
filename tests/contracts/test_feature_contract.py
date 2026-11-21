"""Generic contract every concrete Feature must satisfy (Liskov substitution).

Discovers all concrete :class:`Feature` subclasses in the package, plus a
reference implementation defined here, and checks that each one:

* never changes its value at ``t`` when data at or after ``t`` changes;
* returns one row per forecast time with the declared column names.

New features are covered automatically; nothing to add here.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Sequence
from typing import Self

import numpy as np
import pandas as pd
import pytest

import spacegeo
from spacegeo.common.time import duration
from spacegeo.features.base import Feature


class _ReferenceMean(Feature):
    """Minimal feature so the contract itself is always exercised."""

    input_columns = ("value",)

    @property
    def output_names(self) -> tuple[str, ...]:
        return ("value_mean_6h",)

    @classmethod
    def example(cls) -> Self:
        return cls(lookback=duration(hours=6))

    def _compute_window(self, window: pd.DataFrame, forecast_time: pd.Timestamp) -> Sequence[float]:
        return [float(window["value"].to_numpy().mean())]


def _concrete_features() -> list[type[Feature]]:
    for info in pkgutil.walk_packages(spacegeo.__path__, prefix="spacegeo."):
        importlib.import_module(info.name)
    found: list[type[Feature]] = []
    stack: list[type[Feature]] = list(Feature.__subclasses__())
    while stack:
        cls = stack.pop()
        stack.extend(cls.__subclasses__())
        if not inspect.isabstract(cls):
            found.append(cls)
    return sorted(set(found), key=lambda c: c.__qualname__)


def _synthetic(columns: Sequence[str], seed: int = 0) -> pd.DataFrame:
    index = pd.date_range("2020-01-01", periods=24 * 30, freq="h", tz="UTC")
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        rng.normal(size=(len(index), len(columns))), index=index, columns=list(columns)
    )


FEATURES = _concrete_features()


@pytest.mark.parametrize("feature_cls", FEATURES, ids=lambda c: c.__qualname__)
def test_no_future_leakage(feature_cls: type[Feature]) -> None:
    feature = feature_cls.example()
    data = _synthetic(feature.input_columns)
    t = data.index[len(data) // 2]
    forecast_times = pd.DatetimeIndex([t])

    before = feature.compute(data, forecast_times)

    tampered = data.copy()
    tampered.loc[tampered.index >= t] = 1e9
    after = feature.compute(tampered, forecast_times)

    pd.testing.assert_frame_equal(before, after, obj=f"{feature_cls.__qualname__} at t")


@pytest.mark.parametrize("feature_cls", FEATURES, ids=lambda c: c.__qualname__)
def test_output_shape_and_names(feature_cls: type[Feature]) -> None:
    feature = feature_cls.example()
    data = _synthetic(feature.input_columns)
    forecast_times = data.index[::24]
    out = feature.compute(data, pd.DatetimeIndex(forecast_times))
    assert list(out.columns) == list(feature.output_names)
    assert out.index.equals(forecast_times)


def test_reference_feature_is_discovered() -> None:
    assert _ReferenceMean in FEATURES
