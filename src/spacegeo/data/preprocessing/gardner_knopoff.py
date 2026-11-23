"""Gardner-Knopoff (1974) window declustering."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import pandas as pd

from spacegeo.common.geo import haversine_km
from spacegeo.common.time import duration, require_utc_index
from spacegeo.data.preprocessing.base import PREPROCESSORS, Preprocessor

_LARGE_EVENT_MAG = 6.5


@PREPROCESSORS.register("gardner_knopoff")
class GardnerKnopoffDeclusterer(Preprocessor):
    """Removes events inside the space-time window of a larger event.

    Windows follow the Gardner & Knopoff (1974) fit as tabulated by
    van Stiphout et al. (2012, CORSSA):

    * distance ``L = 10**(0.1238 M + 0.983)`` km
    * time ``T = 10**(0.032 M + 2.7389)`` days if ``M >= 6.5``,
      else ``10**(0.5409 M - 0.547)`` days

    Events are visited from largest to smallest magnitude; every smaller
    event inside a surviving event's window is marked dependent. Only
    independent events (mainshocks) are returned.

    Args:
        include_foreshocks: Also remove events in the window *before* a
            larger event, not just after it.
    """

    def __init__(self, include_foreshocks: bool = True) -> None:
        self._include_foreshocks = include_foreshocks

    @staticmethod
    def distance_window_km(mag: npt.ArrayLike) -> npt.NDArray[np.float64]:
        """Spatial window, km, for magnitude(s) ``mag``."""
        m = np.asarray(mag, dtype=np.float64)
        return 10 ** (0.1238 * m + 0.983)

    @staticmethod
    def time_window_days(mag: npt.ArrayLike) -> npt.NDArray[np.float64]:
        """Temporal window, days, for magnitude(s) ``mag``."""
        m = np.asarray(mag, dtype=np.float64)
        return np.where(
            m >= _LARGE_EVENT_MAG, 10 ** (0.032 * m + 2.7389), 10 ** (0.5409 * m - 0.547)
        )

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return the mainshocks of ``data`` (sorted by time)."""
        if bool(data["mag"].isna().to_numpy().any()):
            raise ValueError("Declustering needs a magnitude for every event; cut first.")
        catalog = data.sort_index()
        dependent = self._dependent_mask(catalog)
        return catalog.loc[~dependent].copy()

    def _dependent_mask(self, catalog: pd.DataFrame) -> npt.NDArray[np.bool_]:
        index = require_utc_index(catalog.index)
        days = np.asarray((index - index[0]) / duration(days=1), dtype=np.float64)
        lat = catalog["lat_deg"].to_numpy(dtype=np.float64)
        lon = catalog["lon_deg"].to_numpy(dtype=np.float64)
        mag = catalog["mag"].to_numpy(dtype=np.float64)
        t_win = self.time_window_days(mag)
        d_win = self.distance_window_km(mag)
        dependent = np.zeros(len(catalog), dtype=bool)
        for i in np.argsort(-mag, kind="stable"):
            if dependent[i]:
                continue
            before = t_win[i] if self._include_foreshocks else 0.0
            lo = int(np.searchsorted(days, days[i] - before, side="left"))
            hi = int(np.searchsorted(days, days[i] + t_win[i], side="right"))
            near = haversine_km(lat[i], lon[i], lat[lo:hi], lon[lo:hi]) <= d_win[i]
            near &= mag[lo:hi] <= mag[i]
            near[i - lo] = False
            dependent[lo:hi] |= near
        return dependent
