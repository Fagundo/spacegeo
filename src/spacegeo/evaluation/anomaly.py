"""Regional seismicity anomaly scan: is a recent window unusually busy or quiet?

Each region's count in an observation window is compared with a count
distribution fitted to that region's own history (a CSEP-style N-test per
region). Within each window, p-values across all regions and both tails are
corrected together with Benjamini-Hochberg, so a flagged region survives the
look-elsewhere effect of scanning many places at once.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Self

import numpy as np
import numpy.typing as npt
import pandas as pd
import yaml
from pydantic import Field, ValidationError

from spacegeo.common.config import BaseConfig
from spacegeo.common.exceptions import ConfigError
from spacegeo.common.fitting import FittableMixin
from spacegeo.common.geo import GeoBox, GeoRegion
from spacegeo.common.stats import benjamini_hochberg
from spacegeo.common.time import TimeWindow, require_utc_index
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
    "log_score",
    "pit",
)
"""``log_score``: natural log of the forecast probability of the observed
count (a proper scoring rule; higher is better). ``pit``: randomized
probability integral transform, uniform on [0, 1] if the forecast is
calibrated."""


class BoxConfig(BaseConfig):
    """One lat/lon box; see :class:`~spacegeo.common.geo.GeoBox`."""

    lat_min_deg: float
    lat_max_deg: float
    lon_min_deg: float
    lon_max_deg: float

    @property
    def box(self) -> GeoBox:
        """The box as a :class:`GeoBox`."""
        return GeoBox(self.lat_min_deg, self.lat_max_deg, self.lon_min_deg, self.lon_max_deg)


class RegionConfig(BaseConfig):
    """A named region made of one or more boxes.

    Attributes:
        name: Region name used in outputs.
        boxes: Pieces of the region (union).
    """

    name: str
    boxes: tuple[BoxConfig, ...] = Field(min_length=1)

    @property
    def geo(self) -> GeoRegion:
        """The region as a :class:`GeoRegion`."""
        return GeoRegion(tuple(b.box for b in self.boxes))

    @classmethod
    def load_all(cls, path: Path) -> tuple[RegionConfig, ...]:
        """The ``regions:`` list of a YAML config, validated and checked disjoint."""
        try:
            raw = yaml.safe_load(path.read_text()) or {}
            regions = tuple(cls.model_validate(r) for r in raw["regions"])
        except (OSError, KeyError, TypeError, yaml.YAMLError, ValidationError) as exc:
            raise ConfigError(f"No valid regions list in {path}: {exc}") from exc
        cls.check_disjoint(regions)
        return regions

    @staticmethod
    def check_disjoint(regions: Sequence[RegionConfig]) -> None:
        """Raise ``ValueError`` if names repeat or any two regions overlap."""
        names = [r.name for r in regions]
        if len(set(names)) != len(names):
            raise ValueError("Region names must be unique.")
        clashes = [
            f"{a.name}/{b.name}"
            for i, a in enumerate(regions)
            for b in regions[i + 1 :]
            if a.geo.intersects(b.geo)
        ]
        if clashes:
            raise ValueError(f"Regions overlap: {', '.join(clashes)}.")


class _RegionEvents:
    """One region's event times (int64 ns, sorted) and magnitudes."""

    def __init__(self, region: RegionConfig, events: pd.DataFrame) -> None:
        local = events.loc[region.geo.contains(events["lat_deg"], events["lon_deg"])].sort_index()
        self.frame = local
        self.times_ns = require_utc_index(local.index).as_unit("ns").asi8
        self.mags = local["mag"].to_numpy(dtype=np.float64)

    def slice(self, window: TimeWindow) -> npt.NDArray[np.float64]:
        lo, hi = np.searchsorted(self.times_ns, [window.start.value, window.end.value])
        return self.mags[lo:hi]


class RegionalAnomalyScanner(FittableMixin):
    """Fits a count model per region once, then scores any later windows.

    Args:
        regions: Regions to scan.
        model_factory: Builds a fresh, unfitted :class:`CountModel`; its
            horizon is the length of every scored window.
        fdr: False-discovery rate used for the ``flag`` column.
        seed: Seed for the randomized PIT (outputs are reproducible).
    """

    def __init__(
        self,
        regions: Sequence[RegionConfig],
        model_factory: Callable[[], CountModel],
        fdr: float = 0.05,
        seed: int = 0,
    ) -> None:
        if not regions:
            raise ValueError("Need at least one region.")
        self._regions = tuple(regions)
        self._model_factory = model_factory
        self._fdr = fdr
        self._models: dict[str, CountModel] = {}
        self._fit_end: pd.Timestamp | None = None
        self._seed = seed

    @property
    def models(self) -> Mapping[str, CountModel]:
        """Fitted count model per region name."""
        self._require_fitted()
        return MappingProxyType(self._models)

    def fit(self, events: pd.DataFrame, baseline: TimeWindow) -> Self:
        """Fit each region's count model on events inside ``baseline``.

        Args:
            events: Catalog with ``lat_deg``, ``lon_deg``, ``mag``; UTC index;
                already cut at Mc (and declustered if the model assumes
                independent events).
            baseline: History to learn from.
        """
        self._models = {
            r.name: self._model_factory().fit(
                ModelData(events=_RegionEvents(r, events).frame, window=baseline)
            )
            for r in self._regions
        }
        self._fit_end = baseline.end
        self._mark_fitted()
        return self

    def score(self, events: pd.DataFrame, windows: Sequence[TimeWindow]) -> pd.DataFrame:
        """Score every region in every window.

        Returns:
            Long frame with ``window_start``, ``region`` and
            :data:`RESULT_COLUMNS`; FDR is applied within each window.
        """
        self._require_fitted()
        self._check_windows(windows)
        per_region = [_RegionEvents(r, events) for r in self._regions]
        rng = np.random.default_rng(self._seed)
        tables = [self._score_window(per_region, w, rng) for w in windows]
        return pd.concat(tables, ignore_index=True)

    def scan(
        self, events: pd.DataFrame, baseline: TimeWindow, observation: TimeWindow
    ) -> pd.DataFrame:
        """Fit on ``baseline`` and score one window.

        Returns:
            One row per region (index ``region``), sorted by ``p_high`` then
            ``p_low``.
        """
        table = self.fit(events, baseline).score(events, [observation])
        table = table.set_index("region").sort_values(["p_high", "p_low"])
        return table.loc[:, list(RESULT_COLUMNS)]

    def _check_windows(self, windows: Sequence[TimeWindow]) -> None:
        horizon = next(iter(self._models.values())).horizon
        for window in windows:
            if window.duration != horizon:
                raise ValueError(f"Window is {window.duration}, model horizon is {horizon}.")
            if self._fit_end is not None and window.start < self._fit_end:
                raise ValueError("Scored windows must start after the fit window ends.")

    def _score_window(
        self, per_region: list[_RegionEvents], window: TimeWindow, rng: np.random.Generator
    ) -> pd.DataFrame:
        rows = [
            self._score_region(r, e, window, rng)
            for r, e in zip(self._regions, per_region, strict=True)
        ]
        table = pd.DataFrame(rows)
        table.insert(0, "window_start", window.start)
        return self._add_fdr(table)

    def _score_region(
        self,
        region: RegionConfig,
        events: _RegionEvents,
        window: TimeWindow,
        rng: np.random.Generator,
    ) -> dict[str, object]:
        model = self._models[region.name]
        mags = events.slice(window)
        observed = int(mags.size)
        expected = model.expected_count()
        below = model.cdf(observed - 1)
        at_or_below = model.cdf(observed)
        return {
            "region": region.name,
            "observed": observed,
            "expected": expected,
            "ratio": observed / expected if expected > 0 else np.inf,
            "p_high": model.survival(observed),
            "p_low": at_or_below,
            "max_mag": float(mags.max()) if observed else np.nan,
            "log_score": self._log_score(model, observed),
            "pit": below + float(rng.uniform()) * (at_or_below - below),
        }

    @staticmethod
    def _log_score(model: CountModel, observed: int) -> float:
        return float(model.log_pmf(observed))  # -inf only if the model rules it out

    def _add_fdr(self, table: pd.DataFrame) -> pd.DataFrame:
        n = len(table)
        q = benjamini_hochberg(np.concatenate([table["p_high"], table["p_low"]]))
        out = table.assign(q_high=q[:n], q_low=q[n:])
        flag = np.where(out["q_high"] <= self._fdr, "excess", "")
        out["flag"] = np.where(out["q_low"] <= self._fdr, "deficit", flag)
        return out
