"""Energy input: Newell et al. (2007) solar wind-magnetosphere coupling function."""

from __future__ import annotations

from typing import Self

import numpy as np
import pandas as pd

from spacegeo.features.base import FEATURES
from spacegeo.features.smoothed_driver import Array, SmoothedDriverFeature


@FEATURES.register("newell_coupling")
class NewellCoupling(SmoothedDriverFeature):
    """Smoothed Newell coupling dPhi/dt = v^(4/3) B_T^(2/3) sin^(8/3)(theta/2).

    Inputs (OMNI2 hourly, GSM): ``speed_km_s``, ``by_gsm_nT``, ``bz_gsm_nT``;
    B_T = sqrt(By^2 + Bz^2) and clock angle theta = atan2(By, Bz). The driver
    is in (km/s)^(4/3) nT^(2/3); the output log ratio is dimensionless.

    Rationale: the rate at which magnetic flux (and so energy) is opened at
    the dayside magnetopause; it best predicts storm and substorm activity,
    ring-current build-up and the induced ground currents that follow. If
    space weather loads faults at all, accumulated energy input is the
    first-order candidate (mechanism E in the pre-registration).
    """

    STEM = "newell"
    input_columns = ("speed_km_s", "by_gsm_nT", "bz_gsm_nT")

    @classmethod
    def example(cls) -> Self:
        """Short scales so the contract tests (30 days of data) see real values."""
        return cls(taus_days=(0.25, 1.0), detrend_days=8.0)

    def _driver(self, rows: pd.DataFrame) -> Array:
        v = rows["speed_km_s"].to_numpy(dtype=np.float64)
        by = rows["by_gsm_nT"].to_numpy(dtype=np.float64)
        bz = rows["bz_gsm_nT"].to_numpy(dtype=np.float64)
        b_t = np.hypot(by, bz)
        sin_half = np.abs(np.sin(np.arctan2(by, bz) / 2.0))
        valid = np.isfinite(v) & np.isfinite(b_t) & (v > 0)
        speed = np.where(valid, v, 1.0)
        value = speed ** (4 / 3) * b_t ** (2 / 3) * sin_half ** (8 / 3)
        return np.where(valid, value, np.nan)
