"""Model interfaces.

Two small interfaces instead of one large one (interface segregation):

* :class:`ForecastModel` - point-process models that score a catalog by
  log-likelihood (ETAS, ETAS + covariates). Basis of information gain.
* :class:`EventProbabilityModel` - models that output P(target event) at
  forecast times (the binary "M >= X within D days" task).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Self

import pandas as pd

from spacegeo.common.fitting import FittableMixin
from spacegeo.common.registry import Registry
from spacegeo.common.time import TimeWindow, require_utc_index


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


FORECAST_MODELS: Registry[ForecastModel] = Registry("forecast model")
PROBABILITY_MODELS: Registry[EventProbabilityModel] = Registry("probability model")
