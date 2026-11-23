"""Count distributions for fixed-length windows."""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from spacegeo.models.base import COUNT_MODELS, CountModel, ModelData

_lgamma = np.vectorize(math.lgamma, otypes=[np.float64])


def _poisson_log_pmf(k: npt.NDArray[np.int64], mean: float) -> npt.NDArray[np.float64]:
    if mean == 0.0:
        return np.where(k == 0, 0.0, -np.inf)
    kf = k.astype(np.float64)
    return kf * math.log(mean) - mean - _lgamma(kf + 1.0)


@COUNT_MODELS.register("poisson")
class PoissonCountModel(CountModel):
    """Homogeneous Poisson counts: rate = events in the fit window / its length.

    Appropriate for a declustered catalog, where events are roughly
    independent. On a raw catalog, aftershock clustering makes it badly
    overconfident; use :class:`NegativeBinomialCountModel` instead.
    """

    _mean: float = 0.0

    def expected_count(self) -> float:
        """Mean count per horizon."""
        self._require_fitted()
        return self._mean

    def _fit(self, data: ModelData) -> None:
        self._mean = data.n_events * float(self.horizon / data.window.duration)

    def _log_pmf(self, k: npt.NDArray[np.int64]) -> npt.NDArray[np.float64]:
        return _poisson_log_pmf(k, self._mean)


@COUNT_MODELS.register("negative_binomial")
class NegativeBinomialCountModel(CountModel):
    """Overdispersed counts, fit by moments to historical window counts.

    The variance of past window counts absorbs aftershock clustering, so
    this is the model for raw (not declustered) catalogs. If the history is
    not overdispersed it reduces to a Poisson.

    Attributes:
        dispersion: Shape ``r``; variance = mean + mean**2 / r. ``inf`` means
            Poisson.
    """

    _mean: float = 0.0
    dispersion: float = math.inf

    def expected_count(self) -> float:
        """Mean count per horizon."""
        self._require_fitted()
        return self._mean

    def _fit(self, data: ModelData) -> None:
        counts = self.window_counts(data).astype(np.float64)
        self._mean = float(counts.mean())
        variance = float(counts.var(ddof=1)) if counts.size > 1 else self._mean
        excess = variance - self._mean
        self.dispersion = self._mean**2 / excess if excess > 0 else math.inf

    def _log_pmf(self, k: npt.NDArray[np.int64]) -> npt.NDArray[np.float64]:
        mean, r = self._mean, self.dispersion
        if mean == 0.0 or math.isinf(r):
            return _poisson_log_pmf(k, mean)
        kf = k.astype(np.float64)
        log_p = math.log(r / (r + mean))
        log_q = math.log(mean / (r + mean))
        return _lgamma(kf + r) - _lgamma(kf + 1.0) - math.lgamma(r) + r * log_p + kf * log_q
