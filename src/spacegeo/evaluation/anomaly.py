"""Regional seismicity anomaly scan: is a recent window unusually busy or quiet?

Each region's count in the observation window is compared with a count
distribution fitted to that region's own history (a CSEP-style N-test per
region). P-values across all regions and both tails are corrected together
with Benjamini-Hochberg, so a "flagged" region survives the look-elsewhere
effect of scanning many places at once.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

import numpy as np
import pandas as pd
from pydantic import AwareDatetime, Field

from spacegeo.common.config import BaseConfig
from spacegeo.common.geo import GeoBox
from spacegeo.common.stats import benjamini_hochberg
from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.models.base import CountModel, ModelData

RESULT_COLUMNS = (
    "observed",
    "expected",
    "ratio",
    "p_high",
    "p_low",
    "q_high",
    "q_low",
    "flag",
    "max_mag",
)


class RegionConfig(BaseConfig):
    """A named lat/lon box; see :class:`~spacegeo.common.geo.GeoBox`."""

    name: str
    lat_min_deg: float
    lat_max_deg: float
    lon_min_deg: float
    lon_max_deg: float

    @property
    def box(self) -> GeoBox:
        """The region as a :class:`GeoBox`."""
        return GeoBox(self.lat_min_deg, self.lat_max_deg, self.lon_min_deg, self.lon_max_deg)


class AnomalyScanConfig(BaseConfig):
    """Settings for a regional anomaly scan.

    Attributes:
        regions: Regions to test (may overlap; each is tested on its own).
        mc: Magnitude of completeness applied to the catalog.
        baseline_start: Start of the history used to fit each region's rate.
        baseline_end: End of that history; must not overlap the observation.
        horizon_days: Observation window length, days.
        fdr: False-discovery rate for flagging, across all tests.
    """

    regions: tuple[RegionConfig, ...] = Field(min_length=1)
    mc: float = 4.5
    baseline_start: AwareDatetime
    baseline_end: AwareDatetime
    horizon_days: float = Field(default=7.0, gt=0)
    fdr: float = Field(default=0.05, gt=0, lt=1)

    @property
    def baseline(self) -> TimeWindow:
        """The baseline as a UTC window."""
        return TimeWindow(to_utc(self.baseline_start), to_utc(self.baseline_end))

    def observation(self, end: datetime | pd.Timestamp) -> TimeWindow:
        """The ``horizon_days`` window ending at ``end`` (exclusive)."""
        stop = to_utc(end)
        return TimeWindow(stop - duration(days=self.horizon_days), stop)


class RegionalAnomalyScanner:
    """Tests each region's recent count against its own history.

    Args:
        regions: Regions to scan.
        model_factory: Builds a fresh, unfitted :class:`CountModel` whose
            horizon equals the observation window length.
        fdr: False-discovery rate used for the ``flag`` column.
    """

    def __init__(
        self,
        regions: Sequence[RegionConfig],
        model_factory: Callable[[], CountModel],
        fdr: float = 0.05,
    ) -> None:
        if not regions:
            raise ValueError("Need at least one region.")
        self._regions = tuple(regions)
        self._model_factory = model_factory
        self._fdr = fdr

    def scan(
        self, events: pd.DataFrame, baseline: TimeWindow, observation: TimeWindow
    ) -> pd.DataFrame:
        """Score every region.

        Args:
            events: Catalog with ``lat_deg``, ``lon_deg`` and ``mag`` columns,
                UTC-indexed, already cut at Mc (and declustered if the model
                assumes independence).
            baseline: History used to fit each region's count model.
            observation: Window being tested; its length must equal the
                model horizon and it must start after the baseline ends.

        Returns:
            One row per region (index ``region``) with columns
            :data:`RESULT_COLUMNS`, sorted by ``p_high`` then ``p_low``.
        """
        self._check_windows(baseline, observation)
        rows = [self._score(region, events, baseline, observation) for region in self._regions]
        table = pd.DataFrame(rows).set_index("region")
        return self._add_fdr(table).sort_values(["p_high", "p_low"]).loc[:, list(RESULT_COLUMNS)]

    def _check_windows(self, baseline: TimeWindow, observation: TimeWindow) -> None:
        horizon = self._model_factory().horizon
        if observation.duration != horizon:
            raise ValueError(f"Observation is {observation.duration}, model horizon is {horizon}.")
        if baseline.end > observation.start:
            raise ValueError("Baseline must end before the observation window starts.")

    def _score(
        self,
        region: RegionConfig,
        events: pd.DataFrame,
        baseline: TimeWindow,
        observation: TimeWindow,
    ) -> dict[str, object]:
        local = events.loc[region.box.contains(events["lat_deg"], events["lon_deg"])]
        model = self._model_factory().fit(ModelData(events=local, window=baseline))
        recent = local.loc[observation.mask(local.index)]
        observed = len(recent)
        expected = model.expected_count()
        return {
            "region": region.name,
            "observed": observed,
            "expected": expected,
            "ratio": observed / expected if expected > 0 else np.inf,
            "p_high": model.survival(observed),
            "p_low": model.cdf(observed),
            "max_mag": float(recent["mag"].max()) if observed else np.nan,
        }

    def _add_fdr(self, table: pd.DataFrame) -> pd.DataFrame:
        n = len(table)
        q = benjamini_hochberg(np.concatenate([table["p_high"], table["p_low"]]))
        out = table.assign(q_high=q[:n], q_low=q[n:])
        flag = np.where(out["q_high"] <= self._fdr, "excess", "")
        out["flag"] = np.where(out["q_low"] <= self._fdr, "deficit", flag)
        return out
