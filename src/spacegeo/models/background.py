"""Spatial background density for point-process models (smoothed seismicity)."""

from __future__ import annotations

from typing import Self

import numpy as np
import numpy.typing as npt

from spacegeo.common.fitting import FittableMixin
from spacegeo.common.geo import GeoRegion, haversine_km

_CHUNK = 256


class KernelBackground(FittableMixin):
    """Weighted, variable-bandwidth Gaussian kernel density over a region.

    Each center ``j`` gets a bandwidth equal to the distance to its
    ``neighbors``-th nearest other center, but at least
    ``min_bandwidth_km`` (Zhuang et al. 2002). The density is normalized so
    it integrates to 1 over the region (Monte Carlo over ``n_mc`` uniform
    points), giving units of km^-2.

    Args:
        region: Region the density lives on.
        neighbors: Nearest-neighbour rank that sets each bandwidth.
        min_bandwidth_km: Smallest bandwidth, km (about the location error).
        n_mc: Monte Carlo points for the normalization.
        seed: RNG seed for the Monte Carlo points.
    """

    def __init__(
        self,
        region: GeoRegion,
        neighbors: int = 5,
        min_bandwidth_km: float = 10.0,
        n_mc: int = 4000,
        seed: int = 0,
    ) -> None:
        self._region = region
        self._neighbors = neighbors
        self._min_bandwidth = min_bandwidth_km
        self._mc_lat, self._mc_lon = region.sample(n_mc, np.random.default_rng(seed))
        self._lat = np.empty(0)
        self._lon = np.empty(0)
        self._bandwidth = np.empty(0)
        self._weights = np.empty(0)
        self._norm = 1.0

    @property
    def bandwidths_km(self) -> npt.NDArray[np.float64]:
        """Per-center bandwidths, km."""
        self._require_fitted()
        return self._bandwidth

    def fit(self, lat_deg: npt.ArrayLike, lon_deg: npt.ArrayLike) -> Self:
        """Set the kernel centers and their bandwidths (weights all 1)."""
        self._lat = np.asarray(lat_deg, dtype=np.float64)
        self._lon = np.asarray(lon_deg, dtype=np.float64)
        if self._lat.size == 0:
            raise ValueError("KernelBackground needs at least one center.")
        self._bandwidth = self._nearest_neighbour_bandwidths()
        self.reweight(np.ones(self._lat.size))
        self._mark_fitted()
        return self

    def reweight(self, weights: npt.ArrayLike) -> Self:
        """Change the center weights (e.g. background probabilities) and renormalize."""
        w = np.asarray(weights, dtype=np.float64)
        if w.shape != self._lat.shape or (w < 0).any() or w.sum() <= 0:
            raise ValueError("Weights must be non-negative, one per center, not all zero.")
        self._weights = w
        self._norm = 1.0
        mean_inside = float(self._raw(self._mc_lat, self._mc_lon).mean())
        self._norm = 1.0 / (mean_inside * self._region.area_km2)
        return self

    def density(self, lat_deg: npt.ArrayLike, lon_deg: npt.ArrayLike) -> npt.NDArray[np.float64]:
        """Density at the points, km^-2 (integrates to 1 over the region)."""
        self._require_fitted()
        return self._raw(
            np.asarray(lat_deg, dtype=np.float64), np.asarray(lon_deg, dtype=np.float64)
        )

    def _raw(
        self, lat: npt.NDArray[np.float64], lon: npt.NDArray[np.float64]
    ) -> npt.NDArray[np.float64]:
        out = np.empty(lat.size)
        h2 = self._bandwidth**2
        coef = self._weights / (2 * np.pi * h2)
        for i in range(0, lat.size, _CHUNK):
            r = haversine_km(
                lat[i : i + _CHUNK, None], lon[i : i + _CHUNK, None], self._lat, self._lon
            )
            out[i : i + _CHUNK] = (coef * np.exp(-0.5 * r**2 / h2)).sum(axis=1)
        return out * self._norm / self._weights.sum()

    def _nearest_neighbour_bandwidths(self) -> npt.NDArray[np.float64]:
        k = min(self._neighbors, self._lat.size - 1)
        if k < 1:
            return np.full(self._lat.size, self._min_bandwidth)
        out = np.empty(self._lat.size)
        for i in range(0, self._lat.size, _CHUNK):
            r = haversine_km(
                self._lat[i : i + _CHUNK, None],
                self._lon[i : i + _CHUNK, None],
                self._lat,
                self._lon,
            )
            out[i : i + _CHUNK] = np.partition(r, k, axis=1)[:, k]  # rank 0 is the point itself
        return np.maximum(out, self._min_bandwidth)
