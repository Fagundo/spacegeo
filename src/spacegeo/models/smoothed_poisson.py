"""Time-independent baseline: constant rate times smoothed seismicity."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt
import pandas as pd

from spacegeo.common.geo import GeoRegion
from spacegeo.common.time import TimeWindow, duration
from spacegeo.models.background import KernelBackground
from spacegeo.models.base import FORECAST_MODELS, ForecastModel, ModelData

_MIN_EVENTS = 2


@FORECAST_MODELS.register("smoothed_poisson")
class SmoothedPoissonModel(ForecastModel):
    """lambda(t, x) = rate * u(x): no clustering in time.

    ``u`` is a variable-bandwidth kernel density of all fit-window events
    (same smoother as ETAS's background), and ``rate`` is their count over
    the window length. It is the reference ETAS is compared against: any
    information gain of ETAS over it comes from modelling clustering.

    Args:
        region: Region the model covers.
        m0: Magnitude threshold.
        neighbors: Nearest-neighbour rank for bandwidths.
        min_bandwidth_km: Smallest bandwidth, km.
    """

    def __init__(
        self,
        region: GeoRegion,
        m0: float = 4.5,
        neighbors: int = 5,
        min_bandwidth_km: float = 10.0,
    ) -> None:
        self._region = region
        self._m0 = m0
        self._background = KernelBackground(region, neighbors, min_bandwidth_km)
        self._rate = 0.0

    @property
    def rate_per_day(self) -> float:
        """Fitted event rate over the region, events/day."""
        self._require_fitted()
        return self._rate

    def log_likelihood_by_window(
        self, data: ModelData, windows: Sequence[TimeWindow]
    ) -> npt.NDArray[np.float64]:
        """Log-likelihood of each window's events."""
        self._require_fitted()
        events = self._local(data)
        out = np.empty(len(windows))
        for i, window in enumerate(windows):
            inside = events.loc[window.mask(events.index)]
            density = self._background.density(inside["lat_deg"], inside["lon_deg"])
            days = window.duration / duration(days=1)
            out[i] = float(np.log(self._rate * density).sum()) - self._rate * days
        return out

    def _log_likelihood(self, data: ModelData) -> float:
        return float(self.log_likelihood_by_window(data, [data.window])[0])

    def _fit(self, data: ModelData) -> None:
        events = self._local(data)
        inside = events.loc[data.window.mask(events.index)]
        if len(inside) < _MIN_EVENTS:
            raise ValueError("SmoothedPoissonModel needs at least 2 events to fit.")
        self._background.fit(inside["lat_deg"], inside["lon_deg"])
        self._rate = len(inside) / (data.window.duration / duration(days=1))

    def _local(self, data: ModelData) -> pd.DataFrame:
        events = data.events
        keep = self._region.contains(events["lat_deg"], events["lon_deg"])
        return events.loc[keep & (events["mag"] >= self._m0 - 1e-9)]
