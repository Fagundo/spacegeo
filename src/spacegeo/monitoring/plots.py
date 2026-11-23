"""Static validation plots (PNG), written deterministically."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure


class ValidationPlots:
    """Calibration (PIT) and detection-power figures for the validation span."""

    def pit(self, histogram: pd.DataFrame, path: Path) -> None:
        """Bar chart of PIT bin shares per test against the uniform line."""
        tests = sorted(histogram["test"].unique())
        fig = Figure(figsize=(4 * len(tests), 3))
        axes = fig.subplots(1, len(tests), sharey=True, squeeze=False)
        for ax, test in zip(axes[0], tests, strict=True):
            table = histogram.loc[histogram["test"] == test]
            width = float((table["bin_high"] - table["bin_low"]).iloc[0])
            ax.bar(table["bin_low"], table["share"], width=width, align="edge", color="#4c78a8")
            ax.axhline(
                1 / len(table), color="#333333", linewidth=1, linestyle="--", label="calibrated"
            )
            ax.set_title(f"{test}: PIT, validation")
            ax.set_xlabel("PIT")
        axes[0][0].set_ylabel("share of region-weeks")
        axes[0][0].legend(frameon=True, loc="lower center")
        self._save(fig, path)

    def power(self, power: pd.DataFrame, path: Path) -> None:
        """Median and inter-quartile detection power across regions vs. burst size."""
        tests = sorted(power["test"].unique())
        fig = Figure(figsize=(5, 3.2))
        ax = fig.subplots()
        for test in tests:
            table = power.loc[power["test"] == test].groupby("added")["power"]
            median, low, high = table.median(), table.quantile(0.25), table.quantile(0.75)
            ax.plot(median.index, median.to_numpy(), marker="o", label=test)
            ax.fill_between(median.index, low.to_numpy(), high.to_numpy(), alpha=0.2)
        ax.axhline(0.8, color="#333333", linewidth=1, linestyle="--")
        ax.set_xscale("log")
        ax.set_xlabel("extra events injected in one week")
        ax.set_ylabel("detection rate (median, IQR over regions)")
        ax.set_ylim(0, 1)
        ax.legend(frameon=False)
        self._save(fig, path)

    @staticmethod
    def _save(fig: Figure, path: Path) -> None:
        fig.tight_layout()
        fig.savefig(path, dpi=110, metadata={"Software": None})
