"""Metric interfaces and the evaluator that applies them."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import ClassVar

from spacegeo.common.registry import Registry
from spacegeo.models.base import ForecastModel, ModelData


class Metric(ABC):
    """Scores a single fitted model."""

    name: ClassVar[str]

    @abstractmethod
    def score(self, model: ForecastModel, data: ModelData) -> float:
        """Return the metric value for ``model`` on ``data.window``."""


class ComparativeMetric(ABC):
    """Scores a fitted model relative to a fitted baseline."""

    name: ClassVar[str]

    @abstractmethod
    def score(self, model: ForecastModel, baseline: ForecastModel, data: ModelData) -> float:
        """Return the metric value for ``model`` versus ``baseline``."""


class Evaluator:
    """Applies a fixed set of metrics to a model (and optional baseline).

    Args:
        metrics: Single-model metrics.
        comparative: Metrics against ``baseline``.
        baseline: Fitted baseline model; required if ``comparative`` is set.
    """

    def __init__(
        self,
        metrics: Sequence[Metric] = (),
        comparative: Sequence[ComparativeMetric] = (),
        baseline: ForecastModel | None = None,
    ) -> None:
        if comparative and baseline is None:
            raise ValueError("Comparative metrics need a baseline model.")
        self._metrics = tuple(metrics)
        self._comparative = tuple(comparative)
        self._baseline = baseline

    def evaluate(self, model: ForecastModel, data: ModelData) -> dict[str, float]:
        """Return ``{metric name: value}`` for every configured metric."""
        results = {m.name: m.score(model, data) for m in self._metrics}
        if self._baseline is not None:
            for metric in self._comparative:
                results[metric.name] = metric.score(model, self._baseline, data)
        return results


METRICS: Registry[Metric] = Registry("metric")
COMPARATIVE_METRICS: Registry[ComparativeMetric] = Registry("comparative metric")
