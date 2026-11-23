"""Seismicity-history features (from one region's catalog, before each forecast time).

Each class sees only events in ``[t - lookback, t)`` (the ``Feature`` base
class enforces this), so none of them can use the window being forecast.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Self

import numpy as np
import pandas as pd

from spacegeo.common.time import duration
from spacegeo.features.base import FEATURES, Feature

_BIN_HALF_WIDTH = 0.05
"""Half the 0.1 magnitude bin, for the Aki-Utsu b-value estimate."""


def _tag(lookback: pd.Timedelta) -> str:
    return f"{int(lookback / duration(days=1))}d"


@FEATURES.register("event_count")
class EventCount(Feature):
    """Number of events at or above ``min_mag`` in the lookback (as log1p too).

    Args:
        lookback: History window.
        min_mag: Magnitude threshold.
    """

    input_columns = ("mag",)

    def __init__(self, lookback: pd.Timedelta, min_mag: float = 4.5) -> None:
        super().__init__(lookback, min_observations=0)
        self._min_mag = min_mag

    @property
    def output_names(self) -> tuple[str, ...]:
        """``count_M<m>_<n>d`` and its log1p."""
        name = f"count_M{self._min_mag:g}_{_tag(self.lookback)}"
        return (name, f"log1p_{name}")

    @classmethod
    def example(cls) -> Self:
        """Default instance for the contract tests."""
        return cls(lookback=duration(days=7))

    def _compute_window(self, window: pd.DataFrame, forecast_time: pd.Timestamp) -> Sequence[float]:
        del forecast_time  # not needed: the window is already before it
        n = int((window["mag"].to_numpy() >= self._min_mag - 1e-9).sum())
        return [float(n), math.log1p(n)]


@FEATURES.register("max_magnitude")
class MaxMagnitude(Feature):
    """Largest magnitude in the lookback (NaN if there were no events)."""

    input_columns = ("mag",)

    def __init__(self, lookback: pd.Timedelta) -> None:
        super().__init__(lookback, min_observations=1)

    @property
    def output_names(self) -> tuple[str, ...]:
        """``max_mag_<n>d``."""
        return (f"max_mag_{_tag(self.lookback)}",)

    @classmethod
    def example(cls) -> Self:
        """Default instance for the contract tests."""
        return cls(lookback=duration(days=30))

    def _compute_window(self, window: pd.DataFrame, forecast_time: pd.Timestamp) -> Sequence[float]:
        del forecast_time  # not needed: the window is already before it
        return [float(np.nanmax(window["mag"].to_numpy(dtype=np.float64)))]


@FEATURES.register("days_since_magnitude")
class DaysSinceMagnitude(Feature):
    """Days since the last event at or above ``min_mag`` (NaN if none in the lookback).

    Args:
        lookback: How far back to look.
        min_mag: Magnitude threshold.
    """

    input_columns = ("mag",)

    def __init__(self, lookback: pd.Timedelta, min_mag: float = 6.0) -> None:
        super().__init__(lookback, min_observations=0)
        self._min_mag = min_mag

    @property
    def output_names(self) -> tuple[str, ...]:
        """``log1p_days_since_M<m>``."""
        return (f"log1p_days_since_M{self._min_mag:g}",)

    @classmethod
    def example(cls) -> Self:
        """Default instance for the contract tests."""
        return cls(lookback=duration(days=60), min_mag=0.5)

    def _compute_window(self, window: pd.DataFrame, forecast_time: pd.Timestamp) -> Sequence[float]:
        hits = window.index[window["mag"].to_numpy() >= self._min_mag - 1e-9]
        if len(hits) == 0:
            return [math.nan]
        return [math.log1p((forecast_time - hits[-1]) / duration(days=1))]


@FEATURES.register("b_value")
class BValue(Feature):
    """Gutenberg-Richter b-value of the last ``n_events`` events above ``mc`` (Aki-Utsu).

    Args:
        lookback: How far back to look for the events.
        mc: Completeness magnitude.
        n_events: Number of most recent events used (fewer -> NaN).
    """

    input_columns = ("mag",)

    def __init__(self, lookback: pd.Timedelta, mc: float = 4.5, n_events: int = 200) -> None:
        super().__init__(lookback, min_observations=n_events)
        self._mc = mc
        self._n = n_events

    @property
    def output_names(self) -> tuple[str, ...]:
        """``b_value_last<n>``."""
        return (f"b_value_last{self._n}",)

    @classmethod
    def example(cls) -> Self:
        """Default instance for the contract tests."""
        return cls(lookback=duration(days=60), mc=-10.0, n_events=20)

    def _compute_window(self, window: pd.DataFrame, forecast_time: pd.Timestamp) -> Sequence[float]:
        del forecast_time  # not needed: the window is already before it
        mags = window["mag"].to_numpy(dtype=np.float64)
        mags = mags[mags >= self._mc - 1e-9][-self._n :]
        if mags.size < self._n:
            return [math.nan]
        excess = float(mags.mean()) - (self._mc - _BIN_HALF_WIDTH)
        return [math.log10(math.e) / excess if excess > 0 else math.nan]


@FEATURES.register("mean_depth")
class MeanDepth(Feature):
    """Mean hypocentral depth in the lookback, km (NaN if no events)."""

    input_columns = ("depth_km",)

    def __init__(self, lookback: pd.Timedelta) -> None:
        super().__init__(lookback, min_observations=1)

    @property
    def output_names(self) -> tuple[str, ...]:
        """``mean_depth_km_<n>d``."""
        return (f"mean_depth_km_{_tag(self.lookback)}",)

    @classmethod
    def example(cls) -> Self:
        """Default instance for the contract tests."""
        return cls(lookback=duration(days=30))

    def _compute_window(self, window: pd.DataFrame, forecast_time: pd.Timestamp) -> Sequence[float]:
        del forecast_time  # not needed: the window is already before it
        return [float(np.nanmean(window["depth_km"].to_numpy(dtype=np.float64)))]
