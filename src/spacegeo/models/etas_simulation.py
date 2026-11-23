"""Simulate catalogs from a space-time ETAS model (branching process)."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import pandas as pd

from spacegeo.common.geo import GeoRegion, destination_point
from spacegeo.common.time import TimeWindow, duration
from spacegeo.models.etas_parameters import EtasParameters, EtasSettings

_MAX_GENERATIONS = 100


class EtasSimulator:
    """Draws synthetic catalogs: uniform background, then offspring generations.

    Magnitudes follow Gutenberg-Richter above ``settings.m0`` with rate
    ``beta``. Offspring times and distances come from the same truncated
    Omori and power-law kernels as the likelihood; offspring outside the
    region are discarded and do not trigger, matching the model.

    Args:
        region: Where events may occur (background is uniform over it).
        params: ETAS parameters.
        beta: Gutenberg-Richter rate, natural log (b-value x ln 10).
        settings: Truncation limits and ``m0``.
    """

    def __init__(
        self,
        region: GeoRegion,
        params: EtasParameters,
        beta: float,
        settings: EtasSettings | None = None,
    ) -> None:
        self._region = region
        self._params = params
        self._beta = beta
        self._settings = settings or EtasSettings()

    def simulate(self, window: TimeWindow, seed: int = 0) -> pd.DataFrame:
        """A catalog for ``window`` (``lat_deg``, ``lon_deg``, ``mag``; UTC index)."""
        rng = np.random.default_rng(seed)
        days = window.duration / duration(days=1)
        n_bg = rng.poisson(self._params.mu * days)
        lat, lon = self._region.sample(n_bg, rng)
        gen = {"t": rng.uniform(0, days, n_bg), "lat": lat, "lon": lon, "m": self._mags(n_bg, rng)}
        events = [gen]
        for _ in range(_MAX_GENERATIONS):
            gen = self._offspring(gen, days, rng)
            if gen["t"].size == 0:
                break
            events.append(gen)
        return self._frame(events, window)

    def _mags(self, n: int, rng: np.random.Generator) -> npt.NDArray[np.float64]:
        return self._settings.m0 + rng.exponential(1.0 / self._beta, n)

    def _offspring(
        self, parents: dict[str, npt.NDArray[np.float64]], days: float, rng: np.random.Generator
    ) -> dict[str, npt.NDArray[np.float64]]:
        p, s = self._params, self._settings
        dm = parents["m"] - s.m0
        counts = rng.poisson(p.a * np.exp(p.alpha * dm))
        idx = np.repeat(np.arange(dm.size), counts)
        dt = p.c * ((1 - rng.uniform(size=idx.size)) ** (1 / (1 - p.p)) - 1)
        v = (1 - rng.uniform(size=idx.size)) ** (1 / (1 - p.q)) - 1
        r = np.sqrt(p.d * np.exp(p.gamma * dm[idx]) * v)
        lat, lon = destination_point(
            parents["lat"][idx], parents["lon"][idx], rng.uniform(0, 2 * np.pi, idx.size), r
        )
        t = parents["t"][idx] + dt
        keep = (
            (dt <= s.t_max_days) & (r <= s.r_max_km) & (t < days) & self._region.contains(lat, lon)
        )
        return {
            "t": t[keep],
            "lat": lat[keep],
            "lon": lon[keep],
            "m": self._mags(int(keep.sum()), rng),
        }

    @staticmethod
    def _frame(
        events: list[dict[str, npt.NDArray[np.float64]]], window: TimeWindow
    ) -> pd.DataFrame:
        t = np.concatenate([e["t"] for e in events])
        index = pd.DatetimeIndex(window.start + pd.to_timedelta(t, unit="D"), name="time")
        frame = pd.DataFrame(
            {
                "lat_deg": np.concatenate([e["lat"] for e in events]),
                "lon_deg": np.concatenate([e["lon"] for e in events]),
                "mag": np.round(np.concatenate([e["m"] for e in events]), 2),
            },
            index=index,
        )
        return frame.sort_index()
