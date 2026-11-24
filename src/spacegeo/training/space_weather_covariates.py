"""Hourly space-weather covariates for the ETAS background experiment."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt
import pandas as pd

from spacegeo.common.time import TimeWindow, duration
from spacegeo.features.base import FEATURES
from spacegeo.features.bz_sigma import BzSigma
from spacegeo.features.dynamic_pressure import DynamicPressure
from spacegeo.features.newell_coupling import NewellCoupling
from spacegeo.features.smoothed_driver import SmoothedDriverFeature
from spacegeo.models.etas_likelihood import EPOCH
from spacegeo.models.modulated_background import HourlyCovariates

Array = npt.NDArray[np.float64]
_REGISTERED = (BzSigma, DynamicPressure, NewellCoupling)
"""Importing these registers them, so configs can name them."""


class SpaceWeatherCovariates:
    """Raw smoothed features on the hourly grid, plus standardising and shifting.

    The raw log ratios are computed once per feature set. Each fit then
    standardises them with training-span statistics and maps missing values
    to 0 (no modulation); the shift test circularly shifts the raw rows first.

    Args:
        space_weather: Hourly OMNI2 frame (UTC, hour starts), only data before
            the end of ``grid``.
        grid: Span of the hourly grid (fit start to validation end).
        train_end: End of the training span; statistics use rows before it.
    """

    def __init__(
        self, space_weather: pd.DataFrame, grid: TimeWindow, train_end: pd.Timestamp
    ) -> None:
        self._data = space_weather.loc[space_weather.index < grid.end]
        self._times = pd.DatetimeIndex(
            pd.date_range(grid.start, grid.end, freq="h", inclusive="left")
        )
        self._train_rows = int((self._times < train_end).sum())
        self._start_day = float((grid.start - EPOCH) / duration(days=1))

    @property
    def n_rows(self) -> int:
        """Hours in the grid."""
        return len(self._times)

    @staticmethod
    def features(
        names: Sequence[str], taus_days: Sequence[float], detrend_days: float, min_fraction: float
    ) -> list[SmoothedDriverFeature]:
        """Instantiate registered smoothed-driver features by name."""
        out: list[SmoothedDriverFeature] = []
        for name in names:
            cls = FEATURES.get(name)
            if not issubclass(cls, SmoothedDriverFeature):
                raise TypeError(f"Feature {name!r} is not a SmoothedDriverFeature.")
            out.append(cls(taus_days, detrend_days, min_fraction))
        return out

    def raw(self, features: Sequence[SmoothedDriverFeature]) -> pd.DataFrame:
        """Unstandardised log ratios at every grid hour (NaN where undefined)."""
        frames = [f.compute(self._data, self._times) for f in features]
        return pd.concat(frames, axis=1)

    def standardised(self, raw: pd.DataFrame, shift_rows: int = 0) -> HourlyCovariates:
        """Standardise with training rows only; NaN -> 0; optional circular shift.

        Args:
            raw: Output of :meth:`raw`.
            shift_rows: Circular shift of the whole grid, in hours.
        """
        values = np.roll(raw.to_numpy(dtype=np.float64), shift_rows, axis=0)
        train = values[: self._train_rows]
        mean, sd = np.nanmean(train, axis=0), np.nanstd(train, axis=0)
        if not (np.isfinite(sd).all() and (sd > 0).all()):
            raise ValueError("A covariate has no variation in the training span.")
        z = np.nan_to_num((values - mean) / sd, nan=0.0)
        return HourlyCovariates(self._start_day, z, tuple(raw.columns))

    def missing_fraction(self, raw: pd.DataFrame) -> dict[str, float]:
        """Share of grid hours with an undefined covariate, per column."""
        shares = np.isnan(raw.to_numpy(dtype=np.float64)).mean(axis=0)
        return dict(zip(map(str, raw.columns), shares.tolist(), strict=True))
