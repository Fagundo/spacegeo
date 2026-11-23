"""Magnitude-of-completeness cut."""

from __future__ import annotations

import pandas as pd

from spacegeo.data.preprocessing.base import PREPROCESSORS, Preprocessor


@PREPROCESSORS.register("magnitude_cut")
class MagnitudeCut(Preprocessor):
    """Keeps events with ``mag >= mc``; events without a magnitude are dropped.

    Args:
        mc: Magnitude of completeness for the catalog era being used. State
            it in the experiment config.
    """

    def __init__(self, mc: float) -> None:
        self._mc = mc

    @property
    def mc(self) -> float:
        """Magnitude of completeness."""
        return self._mc

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return the events at or above ``mc``."""
        return data.loc[data["mag"] >= self._mc].copy()
