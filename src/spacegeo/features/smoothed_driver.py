"""Base for space-weather features: multi-scale smoothing of an hourly driver.

A *driver* is an hourly physical series computed row by row from the input
columns (e.g. Newell coupling from solar-wind speed and IMF). For each
smoothing scale tau the feature is

    log EMA_tau[driver](t) - log EMA_D[driver](t)

where EMA is a gap-aware exponentially weighted mean over rows that ended
before ``t``, truncated at ``window_e_folds * tau`` (at most the lookback D),
and D is a long detrending scale (365 days) that removes the solar cycle.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy.signal import lfilter

from spacegeo.common.time import duration, require_utc_index
from spacegeo.features.base import Feature

Array = npt.NDArray[np.float64]


@dataclass(frozen=True)
class _Average:
    """One exponentially weighted mean: decay per step and window length in steps."""

    decay: float
    steps: int

    @property
    def full_weight(self) -> float:
        """Total weight of a fully observed window: sum of decay**k, k = 1..steps."""
        a = self.decay
        return a * (1.0 - a**self.steps) / (1.0 - a)


class SmoothedDriverFeature(Feature):
    """Log ratio of short-scale to long-scale gap-aware averages of an hourly driver.

    Input rows must be stamped at the start of their interval on a regular
    ``CADENCE`` grid (OMNI2 hourly: hour starts), and forecast times must lie
    on that grid, so every row before ``t`` has fully ended by ``t``.

    A smoothed value is NaN when less than ``min_weight_fraction`` of its
    window weight is observed, or when the average is not positive (the log
    is undefined). Nothing is filled.

    :meth:`compute` is overridden with a recursive-filter implementation
    (exact, not an approximation) because evaluating the per-window
    :meth:`_compute_window` at every hour of 26 years is too slow. Both paths
    give the same numbers (tested), and the leakage contract tests run on the
    fast path.

    Args:
        taus_days: Short smoothing scales (e-folding time), days.
        detrend_days: Long scale and lookback (e-folding time and window), days.
        min_weight_fraction: Minimum observed share of each window's weight.
        window_e_folds: Short averages are truncated at this many e-foldings.
    """

    CADENCE = duration(hours=1)
    STEM: ClassVar[str]
    """Output-name prefix naming the driver and its unit."""

    def __init__(
        self,
        taus_days: Sequence[float] = (1.0, 4.0, 16.0),
        detrend_days: float = 365.0,
        min_weight_fraction: float = 0.5,
        window_e_folds: float = 4.0,
    ) -> None:
        super().__init__(lookback=duration(days=detrend_days))
        if not taus_days or min(taus_days) <= 0 or max(taus_days) >= detrend_days:
            raise ValueError("Need 0 < tau < detrend_days for every smoothing scale.")
        if not 0 < min_weight_fraction <= 1:
            raise ValueError("min_weight_fraction must be in (0, 1].")
        self._taus = tuple(float(t) for t in taus_days)
        self._detrend_days = float(detrend_days)
        self._min_fraction = min_weight_fraction
        steps_per_day = duration(days=1) / self.CADENCE
        long_steps = round(detrend_days * steps_per_day)
        self._averages = tuple(
            _Average(
                np.exp(-1.0 / (tau * steps_per_day)),
                min(round(window_e_folds * tau * steps_per_day), long_steps),
            )
            for tau in self._taus
        )
        self._long = _Average(np.exp(-1.0 / (detrend_days * steps_per_day)), long_steps)

    @property
    def output_names(self) -> tuple[str, ...]:
        """``<stem>_logratio_<tau>d_vs_<detrend>d`` for each scale (dimensionless)."""
        return tuple(
            f"{self.STEM}_logratio_{tau:g}d_vs_{self._detrend_days:g}d" for tau in self._taus
        )

    @abstractmethod
    def _driver(self, rows: pd.DataFrame) -> Array:
        """Hourly driver from ``input_columns``, row by row (NaN where undefined)."""

    def compute(self, data: pd.DataFrame, forecast_times: pd.DatetimeIndex) -> pd.DataFrame:
        """Fast exact path: recursive filters over the whole regular grid.

        Args:
            data: Sorted, UTC, grid-stamped rows containing ``input_columns``.
            forecast_times: UTC forecast times on the same grid.

        Returns:
            Frame indexed by ``forecast_times`` with columns ``output_names``.
        """
        index = self._grid_index(data.index)
        self._grid_index(forecast_times)
        if index.empty:
            return pd.DataFrame(np.nan, index=forecast_times, columns=list(self.output_names))
        start = index[0]
        positions = np.asarray((index - start) / self.CADENCE, dtype=np.int64)
        driver = np.full(int(positions[-1]) + 1, np.nan)
        driver[positions] = self._driver(data.loc[:, list(self.input_columns)])
        ends = np.asarray((forecast_times - start) / self.CADENCE, dtype=np.int64)
        long_mean, long_frac = self._filtered(driver, ends, self._long)
        columns = [
            self._log_ratio(*self._filtered(driver, ends, avg), long_mean, long_frac)
            for avg in self._averages
        ]
        return pd.DataFrame(
            np.column_stack(columns), index=forecast_times, columns=list(self.output_names)
        )

    def _compute_window(self, window: pd.DataFrame, forecast_time: pd.Timestamp) -> Sequence[float]:
        """Reference path: direct weighted sums over the window rows."""
        index = self._grid_index(window.index)
        steps_back = np.asarray((forecast_time - index) / self.CADENCE, dtype=np.int64)
        driver = self._driver(window)
        long_mean, long_frac = self._direct(driver, steps_back, self._long)
        return [
            float(self._log_ratio(*self._direct(driver, steps_back, avg), long_mean, long_frac)[0])
            for avg in self._averages
        ]

    def _log_ratio(self, mean: Array, frac: Array, long_mean: Array, long_frac: Array) -> Array:
        ok = (frac >= self._min_fraction) & (long_frac >= self._min_fraction)
        ok &= (mean > 0) & (long_mean > 0)
        safe = np.where(ok, mean, 1.0) / np.where(ok, long_mean, 1.0)
        return np.where(ok, np.log(safe), np.nan)

    def _grid_index(self, index: pd.Index) -> pd.DatetimeIndex:
        utc = require_utc_index(index)
        step = int(self.CADENCE.value)
        if (np.asarray(utc.as_unit("ns").asi8) % step != 0).any():
            raise ValueError(f"{type(self).__name__} needs times on the {self.CADENCE} grid.")
        return utc

    @staticmethod
    def _filtered(driver: Array, ends: npt.NDArray[np.int64], avg: _Average) -> tuple[Array, Array]:
        """Weighted mean and observed fraction over rows ``[end - steps, end)``."""
        observed = np.isfinite(driver)
        a = avg.decay
        num = _WindowSums(np.where(observed, driver, 0.0), a).at(ends, avg.steps)
        den = _WindowSums(observed.astype(np.float64), a).at(ends, avg.steps)
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = np.where(den > 0, num / np.where(den > 0, den, 1.0), np.nan)
        return mean, den / avg.full_weight

    @staticmethod
    def _direct(
        driver: Array, steps_back: npt.NDArray[np.int64], avg: _Average
    ) -> tuple[Array, Array]:
        inside = (steps_back >= 1) & (steps_back <= avg.steps) & np.isfinite(driver)
        weights = np.where(inside, avg.decay ** steps_back.astype(np.float64), 0.0)
        den = float(weights.sum())
        num = float((weights * np.where(inside, driver, 0.0)).sum())
        mean = np.array([num / den if den > 0 else np.nan])
        return mean, np.array([den / avg.full_weight])


class _WindowSums:
    """Exponentially weighted sums over trailing windows via one recursive filter.

    ``R[k] = sum_{i <= k} a**(k - i) y[i]``; the sum over rows
    ``[end - L, end)`` with weights ``a**(end - i)`` is
    ``a * (R[end - 1] - a**L * R[end - 1 - L])``.
    """

    def __init__(self, values: Array, decay: float) -> None:
        self._decay = decay
        self._running = np.asarray(lfilter([1.0], [1.0, -decay], values), dtype=np.float64)

    def at(self, ends: npt.NDArray[np.int64], steps: int) -> Array:
        """Weighted sums for windows ending (exclusive) at each of ``ends``."""
        a = self._decay
        return a * (self._state(ends - 1) - a**steps * self._state(ends - 1 - steps))

    def _state(self, k: npt.NDArray[np.int64]) -> Array:
        last = self._running.size - 1
        inside = np.clip(k, 0, last)
        beyond = np.maximum(k - last, 0).astype(np.float64)
        values = self._running[inside] * self._decay**beyond
        return np.where(k < 0, 0.0, values)
