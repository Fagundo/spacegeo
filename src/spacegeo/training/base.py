"""Temporal splits and training orchestration.

Splits are always by time, with a gap between spans at least as long as the
longest feature lookback or forecast horizon, so no information crosses
from one span into the next.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from spacegeo.common.time import ZERO, TimestampLike, TimeWindow, to_utc
from spacegeo.models.base import ForecastModel, ModelData


@dataclass(frozen=True)
class TemporalSplit:
    """Train, validation and locked test windows, in time order.

    Attributes:
        train: Fitting span.
        validation: Model-selection span.
        test: Locked span; see ``docs/test-unlocks.md`` before using.
    """

    train: TimeWindow
    validation: TimeWindow
    test: TimeWindow

    def __post_init__(self) -> None:
        ordered = self.train.end <= self.validation.start and self.validation.end <= self.test.start
        if not ordered:
            raise ValueError("Splits must be ordered train < validation < test without overlap.")


class TemporalSplitter:
    """Builds a :class:`TemporalSplit` with a fixed gap between spans.

    Args:
        gap: Dead time between consecutive spans.
    """

    def __init__(self, gap: pd.Timedelta) -> None:
        if gap < ZERO:
            raise ValueError("gap must be non-negative.")
        self._gap = gap

    @property
    def gap(self) -> pd.Timedelta:
        """Dead time between spans."""
        return self._gap

    def split(
        self,
        span: TimeWindow,
        validation_start: TimestampLike,
        test_start: TimestampLike,
    ) -> TemporalSplit:
        """Cut ``span`` into train / validation / test.

        Train ends ``gap`` before validation starts; validation ends ``gap``
        before test starts.
        """
        val_start, test_start_ts = to_utc(validation_start), to_utc(test_start)
        ordered = (
            span.start < val_start - self._gap
            and val_start < test_start_ts - self._gap
            and test_start_ts < span.end
        )
        if not ordered:
            raise ValueError(
                "Split boundaries must be ordered span.start < validation_start < test_start "
                f"< span.end, with each span longer than the gap ({self._gap})."
            )
        return TemporalSplit(
            train=TimeWindow(span.start, val_start - self._gap),
            validation=TimeWindow(val_start, test_start_ts - self._gap),
            test=TimeWindow(test_start_ts, span.end),
        )


class Trainer:
    """Fits a model on the training span of a split."""

    def train(self, model: ForecastModel, data: ModelData, split: TemporalSplit) -> ForecastModel:
        """Fit ``model`` on ``split.train`` and return it."""
        return model.fit(data.restrict(split.train))
