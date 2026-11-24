"""Compression: solar-wind dynamic pressure on the magnetosphere."""

from __future__ import annotations

from typing import Self

import numpy as np
import pandas as pd

from spacegeo.features.base import FEATURES
from spacegeo.features.smoothed_driver import Array, SmoothedDriverFeature


@FEATURES.register("dynamic_pressure")
class DynamicPressure(SmoothedDriverFeature):
    """Smoothed OMNI2 ``pdyn_nPa``: solar-wind flow pressure (nPa).

    Rationale: pressure pulses from CME sheaths and stream interfaces
    compress the magnetosphere (sudden impulses of tens of nT at the ground).
    Tests the compression idea (mechanism C in the pre-registration),
    although the resulting surface pressure change is ~1e-6 Pa.
    """

    STEM = "pdyn_nPa"
    input_columns = ("pdyn_nPa",)

    @classmethod
    def example(cls) -> Self:
        """Short scales so the contract tests (30 days of data) see real values."""
        return cls(taus_days=(0.25, 1.0), detrend_days=8.0)

    def _driver(self, rows: pd.DataFrame) -> Array:
        return rows["pdyn_nPa"].to_numpy(dtype=np.float64)
