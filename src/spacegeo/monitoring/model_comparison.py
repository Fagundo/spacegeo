"""Compare candidate count models on validation weeks with proper scores."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from spacegeo.common.stats import block_bootstrap_ci
from spacegeo.common.time import TimeWindow
from spacegeo.evaluation.anomaly import RegionalAnomalyScanner, RegionConfig
from spacegeo.models.base import CountModel


class ModelComparison:
    """Log score and calibration of each candidate model on each catalog.

    The log score (log probability of the observed count) is a proper
    scoring rule: it is maximized in expectation by the true distribution.
    Information gain is the mean per-region-week log-score difference from
    the ``reference`` model. Intervals are moving-block bootstraps over
    weeks (cross-region averages per week are resampled in blocks), so
    seasonal or sequence-scale autocorrelation is respected.

    Args:
        regions: Regions to scan.
        candidates: Model name -> factory for a fresh model.
        reference: Candidate name used as the information-gain baseline.
        block_weeks: Bootstrap block length in weeks.
        alpha: Nominal tail level for the calibration rates.
    """

    def __init__(
        self,
        regions: Sequence[RegionConfig],
        candidates: Mapping[str, Callable[[], CountModel]],
        reference: str = "poisson",
        block_weeks: int = 13,
        alpha: float = 0.05,
    ) -> None:
        if reference not in candidates:
            raise ValueError(f"Reference model {reference!r} is not a candidate.")
        self._regions = tuple(regions)
        self._candidates = dict(candidates)
        self._reference = reference
        self._block = block_weeks
        self._alpha = alpha

    def compare(
        self, catalogs: Mapping[str, pd.DataFrame], fit: TimeWindow, weeks: Sequence[TimeWindow]
    ) -> pd.DataFrame:
        """One row per (catalog, model).

        Returns:
            Columns: ``mean_log_score`` with ``_lo``/``_hi`` bounds,
            ``info_gain`` (vs. the reference) with bounds, and the two tail
            rates ``rate_p_high_le_alpha`` / ``rate_p_low_le_alpha``.
        """
        rows = []
        for catalog_name, events in catalogs.items():
            scores = {
                name: RegionalAnomalyScanner(self._regions, factory)
                .fit(events, fit)
                .score(events, weeks)
                for name, factory in self._candidates.items()
            }
            reference = self._weekly_mean(scores[self._reference])
            for name, table in scores.items():
                rows.append({"catalog": catalog_name, "model": name, **self._row(table, reference)})
        return pd.DataFrame(rows).set_index(["catalog", "model"])

    @staticmethod
    def _weekly_mean(table: pd.DataFrame) -> pd.Series:
        return pd.Series(table.groupby("window_start")["log_score"].mean())

    def _row(self, table: pd.DataFrame, reference: pd.Series) -> dict[str, float]:
        weekly = self._weekly_mean(table)
        gain = weekly - reference
        return {
            **self._interval("mean_log_score", weekly),
            **self._interval("info_gain", gain),
            "rate_p_high_le_alpha": float((table["p_high"] <= self._alpha).mean()),
            "rate_p_low_le_alpha": float((table["p_low"] <= self._alpha).mean()),
        }

    def _interval(self, name: str, weekly: pd.Series) -> dict[str, float]:
        values = weekly.to_numpy(dtype=np.float64)
        if not np.isfinite(values).all():
            return {name: float(np.mean(values)), f"{name}_lo": np.nan, f"{name}_hi": np.nan}
        low, high = block_bootstrap_ci(values, self._block)
        return {name: float(values.mean()), f"{name}_lo": low, f"{name}_hi": high}
