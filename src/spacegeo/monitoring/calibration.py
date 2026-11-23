"""Calibration summary of weekly scan results (used on the validation span)."""

from __future__ import annotations

import numpy as np
import pandas as pd


class CalibrationSummary:
    """Checks that p-values behave as advertised when nothing unusual happens.

    With no real anomalies, a per-test p-value <= ``alpha`` should occur in
    at most about ``alpha`` of region-weeks (count tests are discrete, so
    usually a bit less). A test is marked calibrated if both tails stay
    within ``tolerance`` x ``alpha``. This is the pre-registered criterion in
    ``docs/experiments/anomaly-scan.md``.

    Args:
        alpha: Nominal per-test level.
        tolerance: Allowed ratio of observed to nominal rate.
    """

    def __init__(self, alpha: float = 0.05, tolerance: float = 1.5) -> None:
        self._alpha = alpha
        self._tolerance = tolerance

    def by_test(self, results: pd.DataFrame) -> pd.DataFrame:
        """One row per test: tail rates, flag rates, bias, and the verdict."""
        a = self._alpha
        table = results.assign(
            high=results["p_high"] <= a,
            low=results["p_low"] <= a,
            excess=results["flag"] == "excess",
            deficit=results["flag"] == "deficit",
        )
        summary = pd.DataFrame(
            table.groupby("test").agg(
                region_weeks=("high", "size"),
                rate_p_high_le_alpha=("high", "mean"),
                rate_p_low_le_alpha=("low", "mean"),
                rate_flag_excess=("excess", "mean"),
                rate_flag_deficit=("deficit", "mean"),
                observed=("observed", "sum"),
                expected=("expected", "sum"),
            )
        )
        summary["observed_over_expected"] = summary["observed"] / summary["expected"]
        summary["mean_log_score"] = table.groupby("test")["log_score"].mean()
        summary["pit_max_bin_deviation"] = self._pit_deviation(results)
        limit = self._tolerance * a
        summary["calibrated"] = (summary["rate_p_high_le_alpha"] <= limit) & (
            summary["rate_p_low_le_alpha"] <= limit
        )
        summary.insert(0, "alpha", a)
        return summary

    def _pit_deviation(self, results: pd.DataFrame, bins: int = 10) -> pd.Series:
        hist = self.pit_histogram(results, bins)
        hist["deviation"] = (hist["share"] - 1 / bins).abs()
        return pd.Series(hist.groupby("test")["deviation"].max())

    @staticmethod
    def pit_histogram(results: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
        """Share of region-weeks per PIT bin, per test (uniform = 1 / bins).

        A U shape means the forecast is overconfident (too narrow), a hump
        means underconfident, a slope means biased.
        """
        edges = np.linspace(0.0, 1.0, bins + 1)
        rows = []
        for test, table in results.groupby("test", sort=True):
            counts, _ = np.histogram(table["pit"].to_numpy(dtype=np.float64), bins=edges)
            share = counts / counts.sum()
            rows += [
                {"test": test, "bin_low": lo, "bin_high": hi, "share": s}
                for lo, hi, s in zip(edges[:-1], edges[1:], share, strict=True)
            ]
        return pd.DataFrame(rows)

    @staticmethod
    def by_region(results: pd.DataFrame) -> pd.DataFrame:
        """Per test and region: total observed / expected and flag counts.

        A ratio well above 1 suggests the rate grew (or the catalog became
        more complete) after training; well below 1, the reverse.
        """
        table = results.assign(
            excess=results["flag"] == "excess", deficit=results["flag"] == "deficit"
        )
        summary = pd.DataFrame(
            table.groupby(["test", "region"]).agg(
                weeks=("observed", "size"),
                observed=("observed", "sum"),
                expected=("expected", "sum"),
                excess_flags=("excess", "sum"),
                deficit_flags=("deficit", "sum"),
            )
        )
        summary["observed_over_expected"] = summary["observed"] / summary["expected"]
        return summary
