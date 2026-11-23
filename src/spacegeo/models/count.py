"""Count distributions for fixed-length windows."""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
import pandas as pd

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


@COUNT_MODELS.register("empirical")
class EmpiricalCountModel(CountModel):
    """Historical window counts, used directly, with a thin heavy tail.

    The pmf is a mixture: weight ``n / (n + pseudo_windows)`` on the
    empirical frequencies of the ``n`` historical windows, the rest on a
    negative binomial fitted to the same counts. The tail keeps every count
    possible, so log scores stay finite and a count above every past window
    gets a small but non-zero p-value instead of exactly 0.

    Args:
        horizon: Window length.
        pseudo_windows: Weight of the negative binomial tail, in windows.
    """

    def __init__(self, horizon: pd.Timedelta, pseudo_windows: float = 1.0) -> None:
        super().__init__(horizon)
        if pseudo_windows <= 0:
            raise ValueError("pseudo_windows must be positive.")
        self._pseudo = pseudo_windows
        self._tail = NegativeBinomialCountModel(horizon)
        self._weight = 1.0
        self._freq: npt.NDArray[np.float64] = np.array([1.0])
        self._upper: npt.NDArray[np.float64] = np.array([1.0])
        self._lower: npt.NDArray[np.float64] = np.array([1.0])

    def expected_count(self) -> float:
        """Mixture mean per horizon."""
        self._require_fitted()
        empirical = float((np.arange(self._freq.size) * self._freq).sum())
        return self._weight * empirical + (1 - self._weight) * self._tail.expected_count()

    def survival(self, n: int) -> float:
        """P(N >= n)."""
        self._require_fitted()
        if n <= 0:
            return 1.0
        empirical = float(self._upper[n]) if n < self._upper.size else 0.0
        return min(1.0, self._weight * empirical + (1 - self._weight) * self._tail.survival(n))

    def cdf(self, n: int) -> float:
        """P(N <= n)."""
        self._require_fitted()
        if n < 0:
            return 0.0
        empirical = float(self._lower[min(n, self._lower.size - 1)])
        return min(1.0, self._weight * empirical + (1 - self._weight) * self._tail.cdf(n))

    def _fit(self, data: ModelData) -> None:
        counts = self.window_counts(data)
        self._tail.fit(data)
        self._weight = counts.size / (counts.size + self._pseudo)
        self._freq = np.bincount(counts).astype(np.float64) / counts.size
        self._upper = np.cumsum(self._freq[::-1])[::-1]  # monotone P(N >= k)
        self._lower = np.cumsum(self._freq)  # monotone P(N <= k)

    def _log_pmf(self, k: npt.NDArray[np.int64]) -> npt.NDArray[np.float64]:
        empirical = np.zeros(k.shape)
        valid = (k >= 0) & (k < self._freq.size)
        empirical[valid] = self._freq[k[valid]]
        tail = self._tail.pmf(k)
        with np.errstate(divide="ignore"):
            return np.log(self._weight * empirical + (1 - self._weight) * tail)
