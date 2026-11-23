"""ETAS vs. smoothed-Poisson baseline experiment over a set of regions.

Fits both models per region on the training span, scores every validation
week with full history, and summarizes information gain with a moving-block
bootstrap over weeks plus time-rescaling residuals.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt
import pandas as pd
from pydantic import AwareDatetime, Field
from scipy import stats

from spacegeo.common.config import BaseConfig
from spacegeo.common.geo import GeoRegion
from spacegeo.common.log import get_logger
from spacegeo.common.stats import block_bootstrap_indices, holm, percentile_interval
from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.models.base import ModelData
from spacegeo.models.etas import EtasModel
from spacegeo.models.etas_parameters import EtasSettings
from spacegeo.models.smoothed_poisson import SmoothedPoissonModel

_log = get_logger(__name__)
_ALPHA = 0.05


class PreRegistration(BaseConfig):
    """What was promised before the run (see the run-experiment skill)."""

    hypothesis: str
    comparison: str
    metric: str
    success: str
    data: str
    variants: int = Field(ge=1)

    def header(self) -> list[str]:
        """Hypothesis and success criterion, as Markdown lines for NOTES.md."""
        return [f"Hypothesis: {self.hypothesis}", f"Success criterion: {self.success}"]


class EtasSettingsConfig(BaseConfig):
    """Configurable subset of :class:`EtasSettings` (``m0`` comes from ``mc``)."""

    t_max_days: float = Field(default=365.0, gt=0)
    r_max_km: float = Field(default=300.0, gt=0)
    burn_in_days: float = Field(default=365.0, ge=0)
    iterations: int = Field(default=5, ge=1)
    tolerance: float = Field(default=0.02, gt=0)

    def settings(self, m0: float) -> EtasSettings:
        """As :class:`EtasSettings` with threshold ``m0``."""
        return EtasSettings(
            m0=m0,
            t_max_days=self.t_max_days,
            r_max_km=self.r_max_km,
            burn_in_days=self.burn_in_days,
            iterations=self.iterations,
            tolerance=self.tolerance,
        )


class ValidationExperimentConfig(BaseConfig):
    """Fields shared by experiments scored on a validation span.

    Attributes:
        prereg: The pre-registration.
        regions_file: YAML file whose ``regions:`` list defines the regions.
        catalog: Committed catalog archive directory.
        mc: Magnitude threshold (= ETAS ``m0``).
        train_start: Start of training.
        val_start: End of training, start of validation.
        val_end: End of validation (exclusive); later data is never loaded.
        week_anchor: Weekday the windows start on.
        bootstrap_block_weeks: Block length of the moving-block bootstrap.
        bootstrap_resamples: Number of bootstrap resamples.
        seed: Seed for the bootstrap (and any other randomness).
        etas: ETAS truncation and fitting settings.
    """

    prereg: PreRegistration
    regions_file: Path
    catalog: Path
    mc: float = 4.5
    train_start: AwareDatetime
    val_start: AwareDatetime
    val_end: AwareDatetime
    week_anchor: str = "W-MON"
    bootstrap_block_weeks: int = Field(default=13, ge=1)
    bootstrap_resamples: int = Field(default=2000, ge=100)
    seed: int = 0
    etas: EtasSettingsConfig = EtasSettingsConfig()

    @property
    def train(self) -> TimeWindow:
        """Training span."""
        return TimeWindow(to_utc(self.train_start), to_utc(self.val_start))

    @property
    def validation(self) -> TimeWindow:
        """Validation span."""
        return TimeWindow(to_utc(self.val_start), to_utc(self.val_end))

    def bootstrap_indices(self, n_weeks: int) -> npt.NDArray[np.int64]:
        """Moving-block bootstrap resamples of week positions, per this config."""
        return block_bootstrap_indices(
            n_weeks, self.bootstrap_block_weeks, self.bootstrap_resamples, self.seed
        )

    def weeks_between(self, start: AwareDatetime, end: AwareDatetime) -> list[TimeWindow]:
        """Whole anchored weeks in ``[start, end)``."""
        lo, hi = to_utc(start), to_utc(end)
        week = duration(days=7)
        starts = pd.date_range(lo, hi, freq=self.week_anchor)
        return [TimeWindow(s, s + week) for s in starts if s + week <= hi]


class EtasExperimentConfig(ValidationExperimentConfig):
    """Config of an ETAS baseline run (``experiment: etas_baseline``).

    The first ``etas.burn_in_days`` of training are history only.
    """

    experiment: Literal["etas_baseline"]

    def weeks(self) -> list[TimeWindow]:
        """Whole anchored weeks inside the validation span."""
        return self.weeks_between(self.val_start, self.val_end)


@dataclass(frozen=True)
class RegionFit:
    """One region's fitted models and validation scores.

    Attributes:
        summary: Scalars for the per-region table.
        weekly: Per validation week: ``n``, ``ll_etas``, ``ll_poisson``.
    """

    summary: dict[str, float | int | str]
    weekly: pd.DataFrame


@dataclass(frozen=True)
class EtasBaselineResult:
    """Everything the run reports.

    Attributes:
        per_region: One row per region: fit, scores, residual test, interval.
        weekly: Long frame: ``week``, ``region``, ``n``, ``ll_etas``, ``ll_poisson``.
        pooled: Pooled information gain and its interval.
    """

    per_region: pd.DataFrame
    weekly: pd.DataFrame
    pooled: dict[str, float]


class EtasBaselineExperiment:
    """Runs the pre-registered ETAS vs. smoothed-Poisson comparison.

    Args:
        config: Experiment config.
        regions: Region name -> geometry.
        catalog: Catalog (``lat_deg``, ``lon_deg``, ``mag``; UTC index).
            Events at or after ``val_end`` are dropped here, so the test span
            cannot be read.
    """

    def __init__(
        self,
        config: EtasExperimentConfig,
        regions: dict[str, GeoRegion],
        catalog: pd.DataFrame,
    ) -> None:
        self._config = config
        self._regions = regions
        self._catalog = catalog.loc[catalog.index < to_utc(config.val_end)]
        self._settings = config.etas.settings(config.mc)
        self._weeks = config.weeks()

    def run(self) -> EtasBaselineResult:
        """Fit and score every region, then summarize."""
        fits = {name: self._fit_region(name, region) for name, region in self._regions.items()}
        weekly = pd.concat(
            [f.weekly.assign(region=name) for name, f in fits.items()], ignore_index=True
        )
        per_region = pd.DataFrame([f.summary for f in fits.values()]).set_index("region")
        per_region, pooled = self._bootstrap(per_region, weekly)
        return EtasBaselineResult(per_region=per_region, weekly=weekly, pooled=pooled)

    def _fit_region(self, name: str, region: GeoRegion) -> RegionFit:
        _log.info("Fitting %s", name)
        train = ModelData(self._catalog, self._config.train)
        etas = EtasModel(region, self._settings).fit(train)
        poisson = SmoothedPoissonModel(region, m0=self._config.mc).fit(train)
        val = ModelData(self._catalog, self._config.validation)
        ll_etas = etas.log_likelihood_by_window(val, self._weeks)
        ll_poisson = poisson.log_likelihood_by_window(val, self._weeks)
        counts = self._weekly_counts(region)
        span = TimeWindow(self._weeks[0].start, self._weeks[-1].end)
        gaps = np.diff(np.concatenate([[0.0], etas.rescaled_times(ModelData(self._catalog, span))]))
        ks = stats.kstest(gaps, "expon") if gaps.size else None
        params = etas.parameters
        summary: dict[str, float | int | str] = {
            "region": name,
            "n_train": int(self._local(region, self._config.train).sum()),
            "n_val": int(counts.sum()),
            **{f"etas_{k}": v for k, v in params.as_dict().items()},
            "beta": etas.beta,
            "b_value": etas.beta / np.log(10),
            "branching_ratio": params.branching_ratio(etas.beta),
            "declustering_iterations": etas.iterations,
            "ll_etas": float(ll_etas.sum()),
            "ll_poisson": float(ll_poisson.sum()),
            "info_gain_per_event": float((ll_etas - ll_poisson).sum() / max(counts.sum(), 1)),
            "ks_statistic": float(ks.statistic) if ks else np.nan,
            "ks_p": float(ks.pvalue) if ks else np.nan,
        }
        weekly = pd.DataFrame(
            {
                "week": [w.start for w in self._weeks],
                "n": counts,
                "ll_etas": ll_etas,
                "ll_poisson": ll_poisson,
            }
        )
        return RegionFit(summary=summary, weekly=weekly)

    def _local(self, region: GeoRegion, window: TimeWindow) -> npt.NDArray[np.bool_]:
        cat = self._catalog
        inside = region.contains(cat["lat_deg"], cat["lon_deg"])
        big_enough = cat["mag"].to_numpy() >= self._config.mc - 1e-9
        return inside & big_enough & window.mask(cat.index)

    def _weekly_counts(self, region: GeoRegion) -> npt.NDArray[np.int64]:
        return np.array([int(self._local(region, w).sum()) for w in self._weeks], dtype=np.int64)

    def _bootstrap(
        self, per_region: pd.DataFrame, weekly: pd.DataFrame
    ) -> tuple[pd.DataFrame, dict[str, float]]:
        diff = weekly.assign(d=weekly["ll_etas"] - weekly["ll_poisson"])
        gain = diff.pivot(index="week", columns="region", values="d").loc[:, per_region.index]
        count = diff.pivot(index="week", columns="region", values="n").loc[:, per_region.index]
        g, n = gain.to_numpy(), count.to_numpy(dtype=np.float64)
        idx = self._config.bootstrap_indices(len(g))
        per_sample = g[idx].sum(axis=1) / np.maximum(n[idx].sum(axis=1), 1.0)
        pooled_sample = g[idx].sum(axis=(1, 2)) / np.maximum(n[idx].sum(axis=(1, 2)), 1.0)
        lows, highs = np.percentile(per_sample, [2.5, 97.5], axis=0)
        p_gain = (per_sample <= 0).mean(axis=0)  # one-sided bootstrap p for gain <= 0
        out = per_region.assign(
            info_gain_lo=lows,
            info_gain_hi=highs,
            p_gain_le_0=p_gain,
            p_gain_holm=holm(p_gain),
            ks_p_holm=holm(per_region["ks_p"].fillna(1.0).to_numpy()),
        )
        low, high = percentile_interval(pooled_sample)
        pooled = {
            "info_gain_per_event": float(g.sum() / n.sum()),
            "info_gain_lo": low,
            "info_gain_hi": high,
            "n_events": float(n.sum()),
            "n_weeks": float(len(g)),
            "n_regions": float(g.shape[1]),
            "regions_gain_ci_above_0": float((lows > 0).sum()),
            "regions_ks_reject_holm_0.05": float((out["ks_p_holm"].to_numpy() <= _ALPHA).sum()),
            "max_branching_ratio": float(per_region["branching_ratio"].to_numpy().max()),
        }
        return out, pooled
