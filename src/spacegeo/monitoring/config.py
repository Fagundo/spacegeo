"""Configuration for the weekly regional anomaly scan."""

from __future__ import annotations

import pandas as pd
from pydantic import AwareDatetime, Field, model_validator

from spacegeo.common.config import BaseConfig
from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.data.preprocessing.regional_completeness import CompletenessSettings
from spacegeo.evaluation.anomaly import RegionConfig


class CompletenessConfig(BaseConfig):
    """Per-region Mc estimation (see ``RegionalCompletenessCut``).

    Attributes:
        correction: Added to the maximum-curvature estimate.
        block_years: Training span is split into blocks this long; the
            largest block estimate is used.
        min_events: Fewest events a block needs to give an estimate.
        fallback: Mc for a region without enough events.
    """

    correction: float = 0.2
    block_years: int = Field(default=5, ge=1)
    min_events: int = Field(default=50, ge=10)
    fallback: float = 4.5

    @property
    def settings(self) -> CompletenessSettings:
        """As the preprocessor's settings object."""
        return CompletenessSettings(
            correction=self.correction,
            block_years=self.block_years,
            min_events=self.min_events,
            fallback=self.fallback,
        )


class WeeklyScanConfig(BaseConfig):
    """Regions, catalog cut and the train / validation / test split.

    The count models are fit on ``[train_start, val_start)`` and checked for
    calibration on every week in ``[val_start, test_start)``. For test weeks
    (``test_start`` onward) they are refit on ``[train_start, test_start)``.

    Attributes:
        regions: Regions to test (may overlap; each is tested on its own).
        catalog_min_magnitude: Lowest magnitude downloaded and stored; also
            the lowest Mc any region may get.
        download_chunk: Pandas frequency for download chunks (``MS`` keeps
            each query under the service's 20,000-event limit at M2.5).
        completeness: How each region's Mc is estimated on the training span.
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
    catalog_min_magnitude: float = 2.5
    download_chunk: str = "MS"
    completeness: CompletenessConfig = CompletenessConfig()
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
        self._check_disjoint()
        return self

    def _check_disjoint(self) -> None:
        names = [r.name for r in self.regions]
        if len(set(names)) != len(names):
            raise ValueError("Region names must be unique.")
        clashes = [
            f"{a.name}/{b.name}"
            for i, a in enumerate(self.regions)
            for b in self.regions[i + 1 :]
            if a.geo.intersects(b.geo)
        ]
        if clashes:
            raise ValueError(f"Regions overlap: {', '.join(clashes)}.")

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
