"""Time-varying background multiplier on top of fixed ETAS fits.

For region r the intensity becomes

    lambda_r(x, t) = c_r * exp(z(t) . beta) * mu_r u_r(x) + triggered_r(x, t)

with triggering and the spatial background u_r held at a fitted
:class:`~spacegeo.models.etas.EtasModel`, ``beta`` shared by all regions and
one normaliser ``c_r`` per region. ``z(t)`` is a set of covariates on an
hourly grid, constant within each hour.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Self

import numpy as np
import numpy.typing as npt
from scipy.optimize import minimize

from spacegeo.common.fitting import FittableMixin
from spacegeo.models.etas import EtasComponents

Array = npt.NDArray[np.float64]
_LOG_C_BOUND = 5.0
_BETA_BOUND = 5.0


@dataclass(frozen=True)
class HourlyCovariates:
    """Covariates on a regular hourly grid; row k covers ``[start + k h, start + (k+1) h)``.

    Attributes:
        start_day: Start of row 0, days since the ETAS epoch.
        values: Covariates, shape ``(hours, k)``; must be finite.
        names: Column names.
    """

    start_day: float
    values: Array
    names: tuple[str, ...]

    STEPS_PER_DAY = 24

    def __post_init__(self) -> None:
        if self.values.ndim != 2 or self.values.shape[1] != len(self.names):  # noqa: PLR2004
            raise ValueError("values must be (hours, len(names)).")
        if not np.isfinite(self.values).all():
            raise ValueError("Covariates must be finite; map missing values before building.")

    @property
    def step_days(self) -> float:
        """Row length, days."""
        return 1.0 / self.STEPS_PER_DAY

    def rows(self, days: Array) -> npt.NDArray[np.int64]:
        """Row covering each time (days since the epoch)."""
        rows = np.floor((np.asarray(days) - self.start_day) * self.STEPS_PER_DAY + 1e-9)
        rows = rows.astype(np.int64)
        if rows.size and (rows.min() < 0 or rows.max() >= len(self.values)):
            raise ValueError("Times fall outside the covariate grid.")
        return rows

    def span_rows(self, t0: float, t1: float) -> npt.NDArray[np.int64]:
        """Rows whose hour starts in ``[t0, t1)`` (spans are whole hours)."""
        lo = round((t0 - self.start_day) * self.STEPS_PER_DAY)
        hi = round((t1 - self.start_day) * self.STEPS_PER_DAY)
        if lo < 0 or hi > len(self.values):
            raise ValueError("Span falls outside the covariate grid.")
        return np.arange(lo, hi)


@dataclass(frozen=True)
class _Stacked:
    """All regions' events in flat arrays."""

    region: npt.NDArray[np.int64]
    z: Array
    background: Array
    triggered: Array
    weight: Array
    mu: Array

    @classmethod
    def build(
        cls,
        regions: Sequence[EtasComponents],
        covariates: HourlyCovariates,
        weights: Sequence[Array] | None,
    ) -> _Stacked:
        times = np.concatenate([c.times for c in regions])
        w = (
            np.concatenate(list(weights))
            if weights is not None
            else np.ones(times.size, dtype=np.float64)
        )
        return cls(
            region=np.concatenate([np.full(c.times.size, i) for i, c in enumerate(regions)]),
            z=covariates.values[covariates.rows(times)],
            background=np.concatenate([c.background for c in regions]),
            triggered=np.concatenate([c.triggered for c in regions]),
            weight=w,
            mu=np.array([c.mu for c in regions]),
        )


class ModulatedBackgroundEtas(FittableMixin):
    """Fits ``beta`` (shared) and ``log c_r`` (per region) by maximum likelihood.

    Args:
        covariates: Hourly covariates covering the fit and scoring spans.
    """

    def __init__(self, covariates: HourlyCovariates) -> None:
        self._cov = covariates
        self._beta = np.zeros(len(covariates.names))
        self._log_c = np.zeros(0)
        self._regions: tuple[str, ...] = ()

    @property
    def beta(self) -> Array:
        """Log rate change per unit of each covariate."""
        self._require_fitted()
        return self._beta.copy()

    @property
    def log_c(self) -> dict[str, float]:
        """Per-region log normaliser."""
        self._require_fitted()
        return dict(zip(self._regions, self._log_c.tolist(), strict=True))

    def fit(
        self,
        regions: Mapping[str, EtasComponents],
        span: tuple[float, float],
        event_weights: Mapping[str, Array] | None = None,
        hour_weights: Array | None = None,
    ) -> Self:
        """Maximise the pooled log-likelihood over ``span`` (days since the epoch).

        Args:
            regions: Fixed ETAS components of the events in ``span``, by region.
            span: Fit span; whole hours inside the covariate grid.
            event_weights: Optional per-event weights (bootstrap multiplicities).
            hour_weights: Optional per-hour weights for the span, same scheme.
        """
        self._regions = tuple(regions)
        comps = [regions[name] for name in self._regions]
        weights = None if event_weights is None else [event_weights[n] for n in self._regions]
        events = _Stacked.build(comps, self._cov, weights)
        hours = self._cov.values[self._cov.span_rows(*span)]
        hw = np.ones(len(hours)) if hour_weights is None else np.asarray(hour_weights, np.float64)
        k = len(self._cov.names)
        result = minimize(
            self._objective,
            np.zeros(k + len(comps)),
            args=(events, hours, hw),
            jac=True,
            method="L-BFGS-B",
            bounds=[(-_BETA_BOUND, _BETA_BOUND)] * k + [(-_LOG_C_BOUND, _LOG_C_BOUND)] * len(comps),
            options={"maxiter": 1000},
        )
        if not (result.success and np.isfinite(result.fun)):
            raise RuntimeError(f"Background-modulation fit failed: {result.message}")
        self._beta, self._log_c = result.x[:k], result.x[k:]
        self._mark_fitted()
        return self

    def gain_by_window(
        self, regions: Mapping[str, EtasComponents], windows: Sequence[tuple[float, float]]
    ) -> Array:
        """Log-likelihood of this model minus plain ETAS, per window and region.

        Args:
            regions: ETAS components of the scored events (fitted regions only).
            windows: Whole-hour ``(t0, t1)`` windows, days since the epoch.

        Returns:
            Array ``(len(windows), len(regions))`` in nats; columns follow ``regions``.
        """
        self._require_fitted()
        multiplier_hours = np.exp(self._cov.values @ self._beta)
        out = np.empty((len(windows), len(regions)))
        log_c = self.log_c
        for j, (name, comp) in enumerate(regions.items()):
            c = np.exp(log_c[name])
            mult = c * np.exp(self._cov.values[self._cov.rows(comp.times)] @ self._beta)
            event_gain = np.log(mult * comp.background + comp.triggered) - np.log(
                comp.background + comp.triggered
            )
            for i, (t0, t1) in enumerate(windows):
                inside = (comp.times >= t0) & (comp.times < t1)
                exposure = multiplier_hours[self._cov.span_rows(t0, t1)].sum() * self._cov.step_days
                compensator = comp.mu * (c * exposure - (t1 - t0))
                out[i, j] = float(event_gain[inside].sum()) - compensator
        return out

    def _objective(
        self, theta: Array, events: _Stacked, hours: Array, hour_weights: Array
    ) -> tuple[float, Array]:
        k = hours.shape[1]
        beta, log_c = theta[:k], theta[k:]
        c = np.exp(log_c)
        lam = c[events.region] * np.exp(events.z @ beta) * events.background
        share = events.weight * lam / (lam + events.triggered)
        m = hour_weights * np.exp(hours @ beta) * self._cov.step_days
        exposure, d_exposure = float(m.sum()), hours.T @ m
        integral = c * events.mu
        loglik = float((events.weight * np.log(lam + events.triggered)).sum()) - float(
            integral.sum() * exposure
        )
        grad_beta = events.z.T @ share - integral.sum() * d_exposure
        grad_c = np.bincount(events.region, weights=share, minlength=c.size) - integral * exposure
        return -loglik, -np.concatenate([grad_beta, grad_c])
