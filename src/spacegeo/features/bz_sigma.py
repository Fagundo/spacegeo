"""Variability: within-hour fluctuation of the IMF north-south component."""

from __future__ import annotations

from typing import Self

import numpy as np
import pandas as pd

from spacegeo.features.base import FEATURES
from spacegeo.features.smoothed_driver import Array, SmoothedDriverFeature


@FEATURES.register("bz_sigma")
class BzSigma(SmoothedDriverFeature):
    """Smoothed OMNI2 ``sigma_bz_nT``: standard deviation of Bz within each hour (nT).

    Rationale: turbulent, rapidly reversing IMF drives bursty reconnection
    and large dB/dt at the ground, inducing stronger telluric currents than
    steady driving of the same mean strength. Tests whether fluctuations, as
    opposed to energy input, matter (mechanism V in the pre-registration).
    """

    STEM = "sigma_bz_nT"
    input_columns = ("sigma_bz_nT",)

    @classmethod
    def example(cls) -> Self:
        """Short scales so the contract tests (30 days of data) see real values."""
        return cls(taus_days=(0.25, 1.0), detrend_days=8.0)

    def _driver(self, rows: pd.DataFrame) -> Array:
        return rows["sigma_bz_nT"].to_numpy(dtype=np.float64)
