"""Calibration summary of weekly scan results (used on the validation span)."""

from __future__ import annotations

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
        limit = self._tolerance * a
        summary["calibrated"] = (summary["rate_p_high_le_alpha"] <= limit) & (
            summary["rate_p_low_le_alpha"] <= limit
        )
        summary.insert(0, "alpha", a)
        return summary

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
