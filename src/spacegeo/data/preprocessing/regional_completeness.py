"""Per-region magnitude-of-completeness cut, estimated on the training span."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self

import numpy as np
import numpy.typing as npt
import pandas as pd

from spacegeo.common.geo import GeoRegion
from spacegeo.common.time import duration, require_utc_index
from spacegeo.data.preprocessing.base import PREPROCESSORS, Preprocessor


@dataclass(frozen=True)
class CompletenessSettings:
    """How Mc is estimated.

    Attributes:
        correction: Added to the maximum-curvature estimate (magnitude units).
        block_years: Length of the blocks the training span is split into.
        min_events: Fewest events a block needs to give an estimate.
        fallback: Mc for a region without enough events.
    """

    correction: float = 0.2
    block_years: int = 5
    min_events: int = 50
    fallback: float = 4.5


@PREPROCESSORS.register("regional_completeness")
class RegionalCompletenessCut(Preprocessor):
    """Keeps each region's events at or above that region's own Mc.

    Mc is estimated in :meth:`fit` (training span only) by maximum curvature
    (the most populated 0.1-magnitude bin) plus a correction (Woessner &
    Wiemer 2005 recommend +0.2, since maximum curvature underestimates Mc).
    Networks improve over time, so the training span is split into blocks
    and the largest block estimate is used: a cut that is complete in the
    earliest block is complete in later ones. Blocks with too few events
    are skipped; a region with no usable block gets the fallback. Events
    outside every region are dropped.

    Args:
        regions: Region name -> geometry.
        floor: Lowest Mc allowed (the catalog's download magnitude).
        overrides: Region name -> fixed Mc, used instead of the estimate.
        settings: Estimation settings.
    """

    BIN_WIDTH = 0.1

    def __init__(
        self,
        regions: Mapping[str, GeoRegion],
        floor: float,
        overrides: Mapping[str, float] | None = None,
        settings: CompletenessSettings | None = None,
    ) -> None:
        self._regions = dict(regions)
        self._floor = floor
        self._overrides = dict(overrides or {})
        self._settings = settings or CompletenessSettings()
        self._mc: dict[str, float] = {}

    @property
    def mc(self) -> Mapping[str, float]:
        """Fitted Mc per region."""
        self._require_fitted()
        return dict(self._mc)

    def fit(self, data: pd.DataFrame) -> Self:
        """Estimate each region's Mc from ``data`` (the training span)."""
        self._mc = {
            name: self._estimate(name, region, data) for name, region in self._regions.items()
        }
        self._mark_fitted()
        return self

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Keep events inside a region and at or above its Mc."""
        self._require_fitted()
        keep = np.zeros(len(data), dtype=bool)
        mags = data["mag"].to_numpy(dtype=np.float64)
        for name, region in self._regions.items():
            inside = region.contains(data["lat_deg"], data["lon_deg"])
            keep |= inside & (mags >= self._mc[name] - 1e-9)
        return data.loc[keep].copy()

    def _estimate(self, name: str, region: GeoRegion, data: pd.DataFrame) -> float:
        if name in self._overrides:
            return self._overrides[name]
        local = data.loc[region.contains(data["lat_deg"], data["lon_deg"])]
        local = local.loc[local["mag"].notna()]
        estimates = [
            self._max_curvature(block) + self._settings.correction
            for block in self._blocks(local)
            if block.size >= self._settings.min_events
        ]
        if not estimates:
            return self._settings.fallback
        return round(max(self._floor, *estimates), 1)

    def _blocks(self, local: pd.DataFrame) -> list[npt.NDArray[np.float64]]:
        if local.empty:
            return []
        index = require_utc_index(local.index)
        years = np.asarray((index - index[0]) / duration(days=365.25), dtype=np.float64)
        block = (years // self._settings.block_years).astype(np.int64)
        mags = local["mag"].to_numpy(dtype=np.float64)
        return [mags[block == b] for b in np.unique(block)]

    def _max_curvature(self, mags: npt.NDArray[np.float64]) -> float:
        binned = np.round(mags / self.BIN_WIDTH).astype(np.int64)
        values, counts = np.unique(binned, return_counts=True)
        return float(values[np.argmax(counts)] * self.BIN_WIDTH)
