"""Do small quakes as triggers improve ETAS forecasts of larger ones?

Two ETAS models per region, fitted on the same training span: one whose
catalog starts at ``low_m0`` (small events trigger too) and one starting at
``mc`` (the usual M4.5 model). Both are scored only on events at or above
``mc`` in the validation span, so their log-likelihoods are comparable.
"""

from __future__ import annotations

from typing import ClassVar, Literal

import numpy as np
import numpy.typing as npt
import pandas as pd
from pydantic import Field

from spacegeo.common.geo import GeoRegion
from spacegeo.common.log import get_logger
from spacegeo.common.time import TimeWindow
from spacegeo.models.base import ModelData
from spacegeo.models.etas import EtasModel
from spacegeo.training.etas_baseline import (
    EtasBaselineExperiment,
    RegionFit,
    ValidationExperimentConfig,
)
from spacegeo.training.etas_report import EtasBaselineReport

_log = get_logger(__name__)


class SmallTriggerConfig(ValidationExperimentConfig):
    """Config of a small-trigger ETAS comparison (``experiment: small_trigger_etas``).

    Attributes:
        low_m0: Completeness threshold of the small-trigger model; ``mc`` is
            both the reference model's threshold and the target magnitude.
    """

    experiment: Literal["small_trigger_etas"]
    low_m0: float = Field(default=3.0)


class SmallTriggerExperiment(EtasBaselineExperiment):
    """ETAS(m0 = low_m0) vs. ETAS(m0 = mc), scored on events >= mc.

    The share of events above ``low_m0`` that reach ``mc`` is taken from the
    training span (empirical, not a Gutenberg-Richter fit), so magnitude-type
    mixing between small and large events does not bias the comparison.

    Args:
        config: Experiment config.
        regions: Region name -> geometry.
        catalog: Combined catalog; events at or after ``val_end`` are dropped.
    """

    def __init__(
        self, config: SmallTriggerConfig, regions: dict[str, GeoRegion], catalog: pd.DataFrame
    ) -> None:
        if config.low_m0 >= config.mc:
            raise ValueError("low_m0 must be below mc.")
        super().__init__(config, regions, catalog)
        self._low = config.etas.settings(config.low_m0)

    def _fit_region(self, name: str, region: GeoRegion) -> RegionFit:
        _log.info("Fitting %s", name)
        train = ModelData(self._catalog, self._config.train)
        small = EtasModel(region, self._low).fit(train)
        large = EtasModel(region, self._settings).fit(train)
        fraction = self._fraction(region)
        val = ModelData(self._catalog, self._config.validation)
        ll_small = small.log_likelihood_above(val, self._weeks, self._config.mc, fraction)
        ll_large = large.log_likelihood_by_window(val, self._weeks)
        counts = self._weekly_counts(region)
        summary: dict[str, float | int | str] = {
            "region": name,
            "n_train_low": int(self._count(region, self._low.m0, self._config.train)),
            "n_train": int(self._local(region, self._config.train).sum()),
            "n_val": int(counts.sum()),
            "fraction_above_mc": fraction,
            "branching_small": small.parameters.branching_ratio(small.beta),
            "branching_large": large.parameters.branching_ratio(large.beta),
            **{f"small_{k}": v for k, v in small.parameters.as_dict().items()},
            **{f"large_{k}": v for k, v in large.parameters.as_dict().items()},
            "ll_small": float(ll_small.sum()),
            "ll_large": float(ll_large.sum()),
            "info_gain_per_event": float((ll_small - ll_large).sum() / max(counts.sum(), 1)),
        }
        return self._region_fit(summary, counts, ll_small, ll_large)

    def _count(self, region: GeoRegion, magnitude: float, window: TimeWindow) -> int:
        return int(self._local(region, window, magnitude).sum())

    def _fraction(self, region: GeoRegion) -> float:
        small = self._count(region, self._low.m0, self._config.train)
        large = self._count(region, self._config.mc, self._config.train)
        if small == 0 or large == 0:
            raise ValueError("Need training events above both thresholds.")
        return large / small

    def _pooled_extras(
        self, per_region: pd.DataFrame, pooled: dict[str, float]
    ) -> tuple[pd.DataFrame, dict[str, float]]:
        branching: npt.NDArray[np.float64] = per_region[
            ["branching_small", "branching_large"]
        ].to_numpy(dtype=np.float64)
        return per_region, {**pooled, "max_branching_ratio": float(branching.max())}


class SmallTriggerReport(EtasBaselineReport):
    """Labels and columns for the small-trigger comparison."""

    TITLE = "Small quakes as ETAS triggers: M3.0 vs. M4.5 catalog"
    MODEL = "ETAS with M>=3 triggers"
    REFERENCE = "ETAS with M>=4.5 only"
    UNIT = "M>=4.5 event"
    COLUMNS: ClassVar[tuple[str, ...]] = (
        "n_train_low",
        "n_train",
        "n_val",
        "fraction_above_mc",
        "info_gain_per_event",
        "info_gain_lo",
        "info_gain_hi",
        "branching_small",
        "branching_large",
        "small_alpha",
        "large_alpha",
    )

    def _bullets(self, pooled: dict[str, float]) -> list[str]:
        return [f"- Largest branching ratio (either model): {pooled['max_branching_ratio']:.2f}"]
