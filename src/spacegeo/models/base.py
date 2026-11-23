"""Model interfaces.

Two small interfaces instead of one large one (interface segregation):

* :class:`ForecastModel` - point-process models that score a catalog by
  log-likelihood (ETAS, ETAS + covariates). Basis of information gain.
* :class:`EventProbabilityModel` - models that output P(target event) at
  forecast times (the binary "M >= X within D days" task).
* :class:`CountModel` - the distribution of the number of events in a
  fixed-length window (regional anomaly monitoring, N-tests).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Self

import numpy as np
import numpy.typing as npt
import pandas as pd

from spacegeo.common.fitting import FittableMixin
from spacegeo.common.registry import Registry
from spacegeo.common.time import TimeWindow, duration, require_utc_index


@dataclass(frozen=True)
class ModelData:
    """Inputs a model sees for one time window.

    Attributes:
        events: Earthquake catalog, UTC-indexed.
        window: Period the model is fitted on or scored over.
        covariates: Optional covariate frame, UTC-indexed.
    """

    events: pd.DataFrame
    window: TimeWindow
    covariates: pd.DataFrame | None = None

    def __post_init__(self) -> None:
        require_utc_index(self.events.index)
        if self.covariates is not None:
            require_utc_index(self.covariates.index)

    @property
    def n_events(self) -> int:
        """Number of events inside :attr:`window`."""
        return int(self.window.mask(self.events.index).sum())

    def restrict(self, window: TimeWindow) -> ModelData:
        """Same data, scored over a different window.

        History before ``window.start`` is kept because point-process models
        need past events to compute rates; only the scoring window changes.
        """
        events = self.events.loc[self.events.index < window.end]
        covariates = None
        if self.covariates is not None:
            covariates = self.covariates.loc[self.covariates.index < window.end]
        return ModelData(events=events, window=window, covariates=covariates)


class ForecastModel(FittableMixin, ABC):
    """A point-process forecast model scored by log-likelihood."""

    def fit(self, data: ModelData) -> Self:
        """Fit parameters on ``data.window``."""
        self._fit(data)
        self._mark_fitted()
        return self

    def log_likelihood(self, data: ModelData) -> float:
        """Log-likelihood of the events in ``data.window`` under the fitted model."""
        self._require_fitted()
        return self._log_likelihood(data)

    @abstractmethod
    def _fit(self, data: ModelData) -> None:
        """Estimate parameters."""

    @abstractmethod
    def _log_likelihood(self, data: ModelData) -> float:
        """Score the window."""


class EventProbabilityModel(FittableMixin, ABC):
    """Predicts the probability of a target event after each forecast time."""

    def fit(self, data: ModelData, targets: pd.Series) -> Self:
        """Fit on ``data`` with binary ``targets`` indexed by forecast time."""
        self._fit(data, targets)
        self._mark_fitted()
        return self

    def predict_proba(self, data: ModelData, forecast_times: pd.DatetimeIndex) -> pd.Series:
        """P(target event) at each forecast time, in [0, 1]."""
        self._require_fitted()
        return self._predict_proba(data, forecast_times)

    @abstractmethod
    def _fit(self, data: ModelData, targets: pd.Series) -> None:
        """Estimate parameters."""

    @abstractmethod
    def _predict_proba(self, data: ModelData, forecast_times: pd.DatetimeIndex) -> pd.Series:
        """Predict probabilities."""


class CountModel(FittableMixin, ABC):
    """Distribution of the event count in a window of length :attr:`horizon`.

    Subclasses implement :meth:`_fit`, :meth:`_log_pmf` and
    :meth:`expected_count`; the base class derives tail probabilities.

    Args:
        horizon: Length of the counting window (e.g. 7 days).
    """

    _TAIL_CHUNK = 2048
    _TAIL_MAX_CHUNKS = 512

    def __init__(self, horizon: pd.Timedelta) -> None:
        if horizon <= duration(seconds=0):
            raise ValueError("Count horizon must be positive.")
        self._horizon = horizon

    @classmethod
    def example(cls) -> Self:
        """A default instance, used by the generic contract tests."""
        return cls(horizon=duration(days=7))

    @property
    def horizon(self) -> pd.Timedelta:
        """Length of the counting window."""
        return self._horizon

    def fit(self, data: ModelData) -> Self:
        """Learn the count distribution from events in ``data.window``."""
        self._fit(data)
        self._mark_fitted()
        return self

    @abstractmethod
    def expected_count(self) -> float:
        """Mean number of events per window."""

    def pmf(self, k: npt.ArrayLike) -> npt.NDArray[np.float64]:
        """P(N = k) for non-negative integer(s) ``k``."""
        self._require_fitted()
        return np.exp(self._log_pmf(np.asarray(k, dtype=np.int64)))

    def cdf(self, n: int) -> float:
        """P(N <= n)."""
        if n < 0:
            return 0.0
        return float(min(1.0, self.pmf(np.arange(n + 1)).sum()))

    def survival(self, n: int) -> float:
        """P(N >= n), summed directly in the upper tail for precision."""
        if n <= 0:
            return 1.0
        if n <= self.expected_count():
            return max(0.0, 1.0 - self.cdf(n - 1))
        total = 0.0
        for chunk in range(self._TAIL_MAX_CHUNKS):
            start = n + chunk * self._TAIL_CHUNK
            part = float(self.pmf(np.arange(start, start + self._TAIL_CHUNK)).sum())
            total += part
            if part <= 1e-16 * max(total, 1e-300):
                break
        return min(1.0, total)

    def window_counts(self, data: ModelData) -> npt.NDArray[np.int64]:
        """Counts in consecutive whole horizons tiling ``data.window``.

        A trailing partial window is dropped.
        """
        n_bins = int(data.window.duration // self._horizon)
        if n_bins < 1:
            raise ValueError("Fit window is shorter than one count horizon.")
        index = require_utc_index(data.events.index)
        inside = index[data.window.mask(index)]
        bins = np.asarray((inside - data.window.start) // self._horizon, dtype=np.int64)
        return np.bincount(bins[bins < n_bins], minlength=n_bins).astype(np.int64)

    @abstractmethod
    def _fit(self, data: ModelData) -> None:
        """Estimate parameters."""

    @abstractmethod
    def _log_pmf(self, k: npt.NDArray[np.int64]) -> npt.NDArray[np.float64]:
        """Return log P(N = k)."""


FORECAST_MODELS: Registry[ForecastModel] = Registry("forecast model")
PROBABILITY_MODELS: Registry[EventProbabilityModel] = Registry("probability model")
COUNT_MODELS: Registry[CountModel] = Registry("count model")
