"""Concrete metrics."""

from __future__ import annotations

from spacegeo.evaluation.base import COMPARATIVE_METRICS, METRICS, ComparativeMetric, Metric
from spacegeo.models.base import ForecastModel, ModelData


@METRICS.register("log_likelihood")
class LogLikelihood(Metric):
    """Total log-likelihood of the window's events."""

    name = "log_likelihood"

    def score(self, model: ForecastModel, data: ModelData) -> float:
        """Return the model's log-likelihood on ``data.window``."""
        return model.log_likelihood(data)


@COMPARATIVE_METRICS.register("information_gain")
class InformationGain(ComparativeMetric):
    """Log-likelihood gain per event over a baseline (nats/event).

    Positive means the model forecasts the window's events better than the
    baseline. This is the project's primary metric (model = ETAS + space
    weather, baseline = ETAS).
    """

    name = "information_gain"

    def score(self, model: ForecastModel, baseline: ForecastModel, data: ModelData) -> float:
        """Return (LL_model - LL_baseline) / n_events.

        Raises:
            ValueError: If the window contains no events.
        """
        if data.n_events == 0:
            raise ValueError("Information gain is undefined for a window with no events.")
        gain = model.log_likelihood(data) - baseline.log_likelihood(data)
        return gain / data.n_events
