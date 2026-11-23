"""Configuration for the weekly regional anomaly scan."""

from __future__ import annotations

import pandas as pd
from pydantic import AwareDatetime, Field, model_validator

from spacegeo.common.config import BaseConfig
from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.evaluation.anomaly import RegionConfig


class WeeklyScanConfig(BaseConfig):
    """Regions, catalog cut and the train / validation / test split.

    The count models are fit on ``[train_start, val_start)`` and checked for
    calibration on every week in ``[val_start, test_start)``. For test weeks
    (``test_start`` onward) they are refit on ``[train_start, test_start)``.

    Attributes:
        regions: Regions to test (may overlap; each is tested on its own).
        mc: Magnitude of completeness applied to the catalog.
        train_start: Start of the history.
        val_start: End of training, start of validation.
        test_start: End of validation, start of live predictions.
        horizon_days: Window length, days.
        fdr: False-discovery rate for flagging, within each window.
        week_anchor: Weekday the windows start on (pandas alias, e.g. ``W-MON``).
        gap_days: Days skipped after each split boundary before the first
            scored window, so short-range clustering does not straddle it.
            Must be at least ``horizon_days``.
    """

    regions: tuple[RegionConfig, ...] = Field(min_length=1)
    mc: float = 4.5
    train_start: AwareDatetime
    val_start: AwareDatetime
    test_start: AwareDatetime
    horizon_days: float = Field(default=7.0, gt=0)
    fdr: float = Field(default=0.05, gt=0, lt=1)
    week_anchor: str = "W-MON"
    gap_days: float = Field(default=7.0, ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> WeeklyScanConfig:
        if not self.train_start < self.val_start < self.test_start:
            raise ValueError("Need train_start < val_start < test_start.")
        if self.gap_days < self.horizon_days:
            raise ValueError("gap_days must be at least horizon_days.")
        return self

    @property
    def train(self) -> TimeWindow:
        """Training span."""
        return TimeWindow(to_utc(self.train_start), to_utc(self.val_start))

    @property
    def validation(self) -> TimeWindow:
        """Validation span."""
        return TimeWindow(to_utc(self.val_start), to_utc(self.test_start))

    @property
    def gap(self) -> pd.Timedelta:
        """Gap after a split boundary."""
        return duration(days=self.gap_days)

    @property
    def refit(self) -> TimeWindow:
        """Training + validation, used to fit the models for test weeks."""
        return TimeWindow(to_utc(self.train_start), to_utc(self.test_start))
