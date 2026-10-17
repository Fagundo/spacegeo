"""Feature interface.

The base class owns the leakage guarantee (template method): for each
forecast time ``t`` it hands the subclass only rows in ``[t - lookback, t)``.
Subclasses implement :meth:`Feature._compute_window` and cannot see the
future. Every concrete feature is also run through the generic leakage
contract test in ``tests/contracts``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import ClassVar, Self

import numpy as np
import pandas as pd

from spacegeo.common.registry import Registry
from spacegeo.common.time import ZERO, require_utc_index


class Feature(ABC):
    """A covariate computed from data strictly before each forecast time.

    Subclasses set :attr:`input_columns`, implement :attr:`output_names`,
    :meth:`_compute_window` and :meth:`example`.

    Args:
        lookback: Width of the history window before each forecast time.
        min_observations: Fewer rows than this in a window yields NaN.
    """

    input_columns: ClassVar[tuple[str, ...]]

    def __init__(self, lookback: pd.Timedelta, min_observations: int = 1) -> None:
        if lookback <= ZERO:
            raise ValueError("lookback must be positive.")
        self._lookback = lookback
        self._min_observations = min_observations

    @property
    def lookback(self) -> pd.Timedelta:
        """History window width."""
        return self._lookback

    @property
    @abstractmethod
    def output_names(self) -> tuple[str, ...]:
        """Output column names, including source, statistic, window and unit."""

    @classmethod
    @abstractmethod
    def example(cls) -> Self:
        """A default instance, used by the generic contract tests."""

    @abstractmethod
    def _compute_window(self, window: pd.DataFrame, forecast_time: pd.Timestamp) -> Sequence[float]:
        """Compute outputs from rows in ``[forecast_time - lookback, forecast_time)``."""

    def compute(self, data: pd.DataFrame, forecast_times: pd.DatetimeIndex) -> pd.DataFrame:
        """Compute the feature at each forecast time.

        Args:
            data: Sorted, UTC-indexed source data containing ``input_columns``.
            forecast_times: UTC times to forecast from.

        Returns:
            Frame indexed by ``forecast_times`` with columns ``output_names``.
        """
        index = require_utc_index(data.index)
        require_utc_index(forecast_times)
        if not index.is_monotonic_increasing:
            raise ValueError("Feature input data must be sorted by time.")
        columns = list(self.input_columns)
        starts = np.atleast_1d(index.searchsorted(forecast_times - self._lookback, side="left"))
        ends = np.atleast_1d(index.searchsorted(forecast_times, side="left"))  # strictly < t
        rows = [
            self._row(data.iloc[start:end][columns], t)
            for start, end, t in zip(starts, ends, forecast_times, strict=True)
        ]
        return pd.DataFrame(rows, index=forecast_times, columns=list(self.output_names))

    def _row(self, window: pd.DataFrame, forecast_time: pd.Timestamp) -> Sequence[float]:
        if len(window) < self._min_observations:
            return [np.nan] * len(self.output_names)
        return self._compute_window(window, forecast_time)


class FeatureSet:
    """Computes several features and joins them column-wise (composite)."""

    def __init__(self, features: Sequence[Feature]) -> None:
        names = [name for feature in features for name in feature.output_names]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate feature output names: {names}")
        self._features = tuple(features)

    @property
    def max_lookback(self) -> pd.Timedelta:
        """Longest lookback in the set; minimum gap for temporal splits."""
        return max((f.lookback for f in self._features), default=ZERO)

    def compute(self, data: pd.DataFrame, forecast_times: pd.DatetimeIndex) -> pd.DataFrame:
        """Compute every feature and concatenate the results."""
        frames = [feature.compute(data, forecast_times) for feature in self._features]
        return pd.concat(frames, axis=1) if frames else pd.DataFrame(index=forecast_times)


FEATURES: Registry[Feature] = Registry("feature")
