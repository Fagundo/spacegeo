"""Space-time ETAS log-likelihood with analytic gradient.

Kept separate from the model class: this module is pure arithmetic on
prepared arrays, the model class handles data, fitting and background.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pandas as pd

from spacegeo.common.geo import GeoRegion, haversine_km
from spacegeo.common.time import duration, require_utc_index, to_utc
from spacegeo.models.etas_parameters import EtasParameters, EtasSettings

EPOCH = to_utc("2000-01-01T00:00Z")
"""Origin of the model's time axis (days)."""

_PAIR_CHUNK = 2000
Array = npt.NDArray[np.float64]


def _days(index: pd.DatetimeIndex) -> Array:
    return np.asarray((require_utc_index(index) - EPOCH) / duration(days=1), dtype=np.float64)


@dataclass(frozen=True)
class EtasCatalog:
    """One region's events as arrays, time-sorted.

    Attributes:
        t: Event times, days since :data:`EPOCH`.
        lat: Latitudes, degrees.
        lon: Longitudes, degrees.
        dm: Magnitude above ``m0``.
        exits: Distance (km) along each of ``n_bearings`` bearings at which
            an offspring would leave the region, capped at ``r_max_km``.
    """

    t: Array
    lat: Array
    lon: Array
    dm: Array
    exits: Array

    @classmethod
    def from_frame(
        cls, events: pd.DataFrame, region: GeoRegion, settings: EtasSettings
    ) -> EtasCatalog:
        """Region events at or above ``m0`` from a catalog frame."""
        inside = region.contains(events["lat_deg"], events["lon_deg"])
        local = events.loc[inside & (events["mag"] >= settings.m0 - 1e-9)].sort_index()
        lat = local["lat_deg"].to_numpy(dtype=np.float64)
        lon = local["lon_deg"].to_numpy(dtype=np.float64)
        bearings = np.linspace(0.0, 2 * np.pi, settings.n_bearings, endpoint=False)
        exits = region.exit_distances_km(lat, lon, bearings, settings.r_max_km, settings.step_km)
        return cls(
            t=_days(pd.DatetimeIndex(local.index)),
            lat=lat,
            lon=lon,
            dm=local["mag"].to_numpy(dtype=np.float64) - settings.m0,
            exits=exits,
        )

    def in_span(self, t0: float, t1: float) -> npt.NDArray[np.int64]:
        """Indices of events with ``t0 <= t < t1``."""
        lo, hi = np.searchsorted(self.t, [t0, t1], side="left")
        return np.arange(lo, hi)


@dataclass(frozen=True)
class EtasPairs:
    """Parent-child pairs within the truncation limits, for a set of targets.

    Attributes:
        targets: Indices of the target events.
        child: Position of each pair's child within ``targets``.
        parent: Catalog index of each pair's parent.
        dt: Time lag, days.
        r2: Squared epicentral distance, km^2.
    """

    targets: npt.NDArray[np.int64]
    child: npt.NDArray[np.int64]
    parent: npt.NDArray[np.int64]
    dt: Array
    r2: Array

    @classmethod
    def build(
        cls, catalog: EtasCatalog, targets: npt.NDArray[np.int64], settings: EtasSettings
    ) -> EtasPairs:
        """All earlier events within ``t_max_days`` and ``r_max_km`` of each target."""
        parts = [
            cls._chunk(catalog, targets, np.arange(i, min(i + _PAIR_CHUNK, targets.size)), settings)
            for i in range(0, targets.size, _PAIR_CHUNK)
        ]
        if not parts:
            empty_i, empty_f = np.empty(0, dtype=np.int64), np.empty(0)
            return cls(targets, empty_i, empty_i, empty_f, empty_f)
        return cls(
            targets,
            np.concatenate([p[0] for p in parts]),
            np.concatenate([p[1] for p in parts]),
            np.concatenate([p[2] for p in parts]),
            np.concatenate([p[3] for p in parts]),
        )

    @staticmethod
    def _chunk(
        catalog: EtasCatalog,
        targets: npt.NDArray[np.int64],
        positions: npt.NDArray[np.int64],
        settings: EtasSettings,
    ) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64], Array, Array]:
        tj = catalog.t[targets[positions]]
        lo = np.searchsorted(catalog.t, tj - settings.t_max_days, side="left")
        hi = np.searchsorted(catalog.t, tj, side="left")
        counts = hi - lo
        child = np.repeat(positions, counts)
        offsets = np.arange(counts.sum()) - np.repeat(np.cumsum(counts) - counts, counts)
        parent = np.repeat(lo, counts) + offsets
        j = targets[child]
        r = haversine_km(catalog.lat[parent], catalog.lon[parent], catalog.lat[j], catalog.lon[j])
        keep = r <= settings.r_max_km
        return child[keep], parent[keep], catalog.t[j][keep] - catalog.t[parent][keep], r[keep] ** 2


class EtasLikelihood:
    """Negative log-likelihood and gradient for one scoring span.

    Args:
        catalog: Region events (parents and targets).
        pairs: Pairs for the targets in ``[t0, t1)``.
        background: Background density u(x) at each target, km^-2.
        span: ``(t0, t1)`` in days since :data:`EPOCH`.
        settings: Truncation limits.
    """

    def __init__(
        self,
        catalog: EtasCatalog,
        pairs: EtasPairs,
        background: Array,
        span: tuple[float, float],
        settings: EtasSettings,
    ) -> None:
        self._cat = catalog
        self._pairs = pairs
        self._u = background
        self._t0, self._t1 = span
        self._settings = settings
        self._parents = catalog.in_span(span[0] - settings.t_max_days, span[1])

    @property
    def targets(self) -> npt.NDArray[np.int64]:
        """Catalog indices of the scored events."""
        return self._pairs.targets

    def intensities(self, params: EtasParameters) -> tuple[Array, Array]:
        """Total intensity and its background part at each target, per day per km^2."""
        trig = self._pair_terms(params)[0]
        triggered = np.bincount(self._pairs.child, weights=trig, minlength=self._u.size)
        background = params.mu * self._u
        return background + triggered, background

    def target_log_terms(self, params: EtasParameters) -> Array:
        """Log lambda at each target."""
        return np.log(self.intensities(params)[0])

    def integral(self, params: EtasParameters, t0: float, t1: float) -> float:
        """Expected number of events in ``[t0, t1)`` inside the region."""
        idx = self._cat.in_span(t0 - self._settings.t_max_days, t1)
        k, f_in, dg = self._parent_terms(params, idx, t0, t1)
        return params.mu * (t1 - t0) + float((k * f_in * dg).sum())

    def history_integral(self, params: EtasParameters, t0: float, t1: float) -> float:
        """Expected events in ``[t0, t1)`` from the background and events before ``t0`` only.

        Unlike :meth:`integral`, events inside the window do not contribute,
        so this is a forecast made at ``t0`` (it leaves out cascades that
        start inside the window).
        """
        idx = self._cat.in_span(t0 - self._settings.t_max_days, t0)
        k, f_in, dg = self._parent_terms(params, idx, t0, t1)
        return params.mu * (t1 - t0) + float((k * f_in * dg).sum())

    def value_and_grad(self, theta: npt.ArrayLike) -> tuple[float, Array]:
        """Negative log-likelihood and its gradient in optimizer coordinates."""
        params = EtasParameters.from_vector(theta)
        log_sum, grad_log = self._log_term_and_grad(params)
        integral, grad_int = self._integral_and_grad(params)
        return -(log_sum - integral), -(grad_log - grad_int)

    def _pair_terms(self, params: EtasParameters) -> tuple[Array, Array, Array]:
        p = self._pairs
        dm = self._cat.dm[p.parent]
        sigma2 = params.d * np.exp(params.gamma * dm)
        ratio = p.r2 / sigma2
        log_g = np.log((params.p - 1) / params.c) - params.p * np.log1p(p.dt / params.c)
        log_f = np.log((params.q - 1) / (np.pi * sigma2)) - params.q * np.log1p(ratio)
        trig = np.exp(np.log(params.a) + params.alpha * dm + log_g + log_f)
        return trig, dm, ratio

    def _log_term_and_grad(self, params: EtasParameters) -> tuple[float, Array]:
        p = self._pairs
        trig, dm, ratio = self._pair_terms(params)
        lam = params.mu * self._u + np.bincount(p.child, weights=trig, minlength=self._u.size)
        inv = 1.0 / lam[p.child]
        s = p.dt
        spatial = -1.0 + params.q * ratio / (1.0 + ratio)
        factors = (
            np.ones_like(trig),
            params.alpha * dm,
            -1.0 + params.p * s / (params.c + s),
            1.0 - (params.p - 1) * np.log1p(s / params.c),
            spatial,
            spatial * params.gamma * dm,
            1.0 - (params.q - 1) * np.log1p(ratio),
        )
        grad = np.empty(8)
        grad[0] = float((params.mu * self._u / lam).sum())
        grad[1:] = [float((trig * inv * fac).sum()) for fac in factors]
        return float(np.log(lam).sum()), grad

    def _parent_terms(
        self, params: EtasParameters, idx: npt.NDArray[np.int64], t0: float, t1: float
    ) -> tuple[Array, Array, Array]:
        dm = self._cat.dm[idx]
        kappa = params.a * np.exp(params.alpha * dm)
        sigma2 = params.d * np.exp(params.gamma * dm)
        y = 1.0 + self._cat.exits[idx] ** 2 / sigma2[:, None]
        f_in = (1.0 - y ** (1.0 - params.q)).mean(axis=1)
        dg = self._omori_cdf(params, t1 - self._cat.t[idx]) - self._omori_cdf(
            params, t0 - self._cat.t[idx]
        )
        return kappa, f_in, dg

    def _omori_cdf(self, params: EtasParameters, s: Array) -> Array:
        clipped = np.clip(s, 0.0, self._settings.t_max_days)
        return 1.0 - (1.0 + clipped / params.c) ** (1.0 - params.p)

    def _integral_and_grad(self, params: EtasParameters) -> tuple[float, Array]:
        idx = self._parents
        kappa, f_in, dg = self._parent_terms(params, idx, self._t0, self._t1)
        dm = self._cat.dm[idx]
        terms = kappa * f_in * dg
        d_dg = self._omori_grad(params, self._t1 - self._cat.t[idx]) - self._omori_grad(
            params, self._t0 - self._cat.t[idx]
        )
        d_fin = self._fin_grad(params, idx)
        grad = np.empty(8)
        grad[0] = params.mu * (self._t1 - self._t0)
        grad[1] = float(terms.sum())
        grad[2] = float((terms * params.alpha * dm).sum())
        grad[3] = float((kappa * f_in * d_dg[0]).sum())
        grad[4] = float((kappa * f_in * d_dg[1]).sum())
        grad[5] = float((kappa * dg * d_fin[0]).sum())
        grad[6] = float((kappa * dg * d_fin[0] * params.gamma * dm).sum())
        grad[7] = float((kappa * dg * d_fin[1]).sum())
        return params.mu * (self._t1 - self._t0) + float(terms.sum()), grad

    def _omori_grad(self, params: EtasParameters, s: Array) -> Array:
        """D G / d log c and d G / d log(p - 1), stacked."""
        x = np.clip(s, 0.0, self._settings.t_max_days) / params.c
        base = 1.0 + x
        d_logc = (1.0 - params.p) * base ** (-params.p) * x
        d_logp = (params.p - 1) * base ** (1.0 - params.p) * np.log(base)
        return np.stack([d_logc, d_logp])

    def _fin_grad(self, params: EtasParameters, idx: npt.NDArray[np.int64]) -> Array:
        """D F_in / d log sigma^2 and d F_in / d log(q - 1), stacked."""
        sigma2 = params.d * np.exp(params.gamma * self._cat.dm[idx])
        b2 = self._cat.exits[idx] ** 2 / sigma2[:, None]
        y = 1.0 + b2
        d_log_sigma2 = (-(params.q - 1) * y ** (-params.q) * b2).mean(axis=1)
        d_logq = ((params.q - 1) * y ** (1.0 - params.q) * np.log(y)).mean(axis=1)
        return np.stack([d_log_sigma2, d_logq])
