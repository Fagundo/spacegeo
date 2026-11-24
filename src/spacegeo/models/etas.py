"""Space-time ETAS forecast model for one region."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

import numpy as np
import numpy.typing as npt
from scipy.optimize import minimize

from spacegeo.common.geo import GeoRegion
from spacegeo.common.log import get_logger
from spacegeo.common.time import TimeWindow, duration
from spacegeo.models.background import KernelBackground
from spacegeo.models.base import FORECAST_MODELS, ForecastModel, ModelData
from spacegeo.models.etas_likelihood import EPOCH, EtasCatalog, EtasLikelihood, EtasPairs
from spacegeo.models.etas_parameters import EtasParameters, EtasSettings

_log = get_logger(__name__)
_MIN_EVENTS = 20
_BOUNDS = [(-12, 8), (-12, 3), (-4, 1.5), (-12, 1), (-7, 1), (-5, 12), (-5, 1.5), (-5, 2)]
"""Optimizer bounds on the log coordinates of :class:`EtasParameters`."""


def _span(window: TimeWindow) -> tuple[float, float]:
    return (window.start - EPOCH) / duration(days=1), (window.end - EPOCH) / duration(days=1)


@dataclass(frozen=True)
class EtasComponents:
    """A fitted ETAS intensity split into background and triggered parts at each event.

    Lets other models change the background (e.g. a time-varying multiplier)
    while keeping the triggering of a fitted ETAS model fixed.

    Attributes:
        times: Event times, days since :data:`EPOCH`, time-sorted.
        background: Background intensity mu * u(x) at each event, per day per km^2.
        triggered: Triggered intensity at each event, per day per km^2.
        mu: Background rate over the whole region, events per day.
    """

    times: npt.NDArray[np.float64]
    background: npt.NDArray[np.float64]
    triggered: npt.NDArray[np.float64]
    mu: float


@FORECAST_MODELS.register("etas")
class EtasModel(ForecastModel):
    """Ogata's space-time ETAS model with Zhuang-style stochastic declustering.

    Fitting alternates two steps on the fit window (after a burn-in that
    only supplies history): (1) maximum likelihood for the eight
    :class:`EtasParameters` with the background density held fixed, using
    L-BFGS-B with an analytic gradient; (2) re-estimating the background
    density by kernel smoothing, weighting each event by its probability of
    being a background event. Triggering is truncated in time and distance
    (``EtasSettings``), and the share of each event's offspring kernel that
    falls inside the region is accounted for in the integral term.

    Only events inside ``region`` and at or above ``settings.m0`` are used,
    both as parents and as targets. Scores exclude the magnitude
    distribution (it is identical across the models compared).

    Args:
        region: Region the model covers.
        settings: Truncation and fitting choices.
    """

    def __init__(self, region: GeoRegion, settings: EtasSettings | None = None) -> None:
        self._region = region
        self._settings = settings or EtasSettings()
        self._background = KernelBackground(
            region, self._settings.neighbors, self._settings.min_bandwidth_km
        )
        self._params: EtasParameters | None = None
        self._phi = np.empty(0)
        self._beta = np.nan
        self._iterations = 0

    @property
    def parameters(self) -> EtasParameters:
        """Fitted parameters."""
        self._require_fitted()
        if self._params is None:
            raise RuntimeError("ETAS parameters missing after fit.")
        return self._params

    @property
    def beta(self) -> float:
        """Gutenberg-Richter rate (natural log) of the fit events (Aki-Utsu, 0.1 bins)."""
        self._require_fitted()
        return self._beta

    @property
    def background_probabilities(self) -> npt.NDArray[np.float64]:
        """Probability each fit-window event is a background event."""
        self._require_fitted()
        return self._phi

    @property
    def iterations(self) -> int:
        """Declustering iterations used."""
        return self._iterations

    def log_likelihood_by_window(
        self, data: ModelData, windows: Sequence[TimeWindow]
    ) -> npt.NDArray[np.float64]:
        """Log-likelihood of each window's events, using all earlier history."""
        return self.log_likelihood_above(data, windows, self._settings.m0, 1.0)

    def log_likelihood_above(
        self,
        data: ModelData,
        windows: Sequence[TimeWindow],
        magnitude: float,
        fraction: float,
    ) -> npt.NDArray[np.float64]:
        """Log-likelihood of only the events at or above ``magnitude`` in each window.

        Every event at or above ``m0`` still triggers. The rate of target
        events is the ETAS rate times ``fraction``, the share of events above
        ``m0`` that reach ``magnitude`` (magnitudes independent of the
        triggering history, as ETAS assumes). With ``magnitude = m0`` and
        ``fraction = 1`` this is the ordinary log-likelihood, so models with
        different ``m0`` can be compared on the same target events.

        Args:
            data: Catalog (all history is used).
            windows: Scoring windows, time-ordered.
            magnitude: Smallest target magnitude (>= ``m0``).
            fraction: P(M >= magnitude | M >= m0), in (0, 1].
        """
        self._require_fitted()
        if magnitude < self._settings.m0 - 1e-9 or not 0 < fraction <= 1:
            raise ValueError("Need magnitude >= m0 and 0 < fraction <= 1.")
        if not windows:
            return np.empty(0)
        catalog = EtasCatalog.from_frame(data.events, self._region, self._settings)
        start, end = _span(windows[0])[0], max(_span(w)[1] for w in windows)
        lik = self._likelihood(catalog, (start, end), magnitude - self._settings.m0)
        logs = lik.target_log_terms(self.parameters) + np.log(fraction)
        times = catalog.t[lik.targets]
        out = np.empty(len(windows))
        for i, window in enumerate(windows):
            t0, t1 = _span(window)
            inside = (times >= t0) & (times < t1)
            compensator = fraction * lik.integral(self.parameters, t0, t1)
            out[i] = float(logs[inside].sum()) - compensator
        return out

    def components(self, data: ModelData) -> EtasComponents:
        """Background and triggered intensity at each event in ``data.window``.

        All earlier events in ``data`` act as parents.
        """
        self._require_fitted()
        catalog = EtasCatalog.from_frame(data.events, self._region, self._settings)
        lik = self._likelihood(catalog, _span(data.window))
        total, background = lik.intensities(self.parameters)
        return EtasComponents(
            times=catalog.t[lik.targets],
            background=background,
            triggered=total - background,
            mu=self.parameters.mu,
        )

    def rescaled_times(self, data: ModelData) -> npt.NDArray[np.float64]:
        """Compensator Lambda(t_i) at each event in ``data.window`` (time rescaling).

        Under a correct model the values form a unit-rate Poisson process, so
        their successive differences are Exp(1).
        """
        self._require_fitted()
        catalog = EtasCatalog.from_frame(data.events, self._region, self._settings)
        t0, t1 = _span(data.window)
        lik = self._likelihood(catalog, (t0, t1))
        times = catalog.t[catalog.in_span(t0, t1)]
        edges = np.concatenate([[t0], times])
        steps = [lik.integral(self.parameters, a, b) for a, b in pairwise(edges)]
        return np.cumsum(np.asarray(steps, dtype=np.float64))

    def _log_likelihood(self, data: ModelData) -> float:
        return float(self.log_likelihood_by_window(data, [data.window])[0])

    def _likelihood(
        self, catalog: EtasCatalog, span: tuple[float, float], min_dm: float = 0.0
    ) -> EtasLikelihood:
        targets = catalog.in_span(*span)
        targets = targets[catalog.dm[targets] >= min_dm - 1e-9]
        pairs = EtasPairs.build(catalog, targets, self._settings)
        background = self._background.density(catalog.lat[targets], catalog.lon[targets])
        return EtasLikelihood(catalog, pairs, background, span, self._settings)

    def _fit(self, data: ModelData) -> None:
        catalog = EtasCatalog.from_frame(data.events, self._region, self._settings)
        t0, t1 = _span(data.window)
        span = (t0 + self._settings.burn_in_days, t1)
        targets = catalog.in_span(*span)
        if targets.size < _MIN_EVENTS:
            raise ValueError(
                f"ETAS needs at least {_MIN_EVENTS} events to fit, got {targets.size}."
            )
        self._beta = 1.0 / (float(catalog.dm[targets].mean()) + 0.05)
        self._background.fit(catalog.lat[targets], catalog.lon[targets])
        pairs = EtasPairs.build(catalog, targets, self._settings)
        theta = self._settings.initial(targets.size, span[1] - span[0]).to_vector()
        phi = np.ones(targets.size)
        for iteration in range(1, self._settings.iterations + 1):
            self._background.reweight(phi)
            background = self._background.density(catalog.lat[targets], catalog.lon[targets])
            lik = EtasLikelihood(catalog, pairs, background, span, self._settings)
            theta = self._optimize(lik, theta)
            total, bg = lik.intensities(EtasParameters.from_vector(theta))
            new_phi = np.clip(bg / total, 1e-6, 1.0)
            change = float(np.abs(new_phi - phi).max())
            phi = new_phi
            self._iterations = iteration
            _log.info(
                "ETAS iteration %d: max background-probability change %.3f", iteration, change
            )
            if change < self._settings.tolerance:
                break
        self._params = EtasParameters.from_vector(theta)
        self._phi = phi

    @staticmethod
    def _optimize(lik: EtasLikelihood, theta: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        result = minimize(
            lik.value_and_grad,
            theta,
            jac=True,
            method="L-BFGS-B",
            bounds=_BOUNDS,
            options={"maxiter": 500},
        )
        if not np.isfinite(result.fun):
            raise RuntimeError(f"ETAS optimization failed: {result.message}")
        return np.asarray(result.x, dtype=np.float64)
