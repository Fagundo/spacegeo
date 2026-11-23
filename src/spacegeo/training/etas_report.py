"""Write a two-model ETAS comparison run: tables, metrics, plots and NOTES.md."""

from __future__ import annotations

from typing import ClassVar

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from spacegeo.common.run import RunDirectory, markdown_table
from spacegeo.training.etas_baseline import EtasBaselineResult, ValidationExperimentConfig


class EtasBaselineReport:
    """Turns an :class:`EtasBaselineResult` into run-directory files.

    Subclasses change the labels, the per-region columns and the pooled
    bullet points for other model pairs.
    """

    TITLE = "ETAS baseline, Ring of Fire"
    MODEL = "ETAS"
    REFERENCE = "smoothed Poisson"
    UNIT = "event"
    COLUMNS: ClassVar[tuple[str, ...]] = (
        "n_train",
        "n_val",
        "info_gain_per_event",
        "info_gain_lo",
        "info_gain_hi",
        "branching_ratio",
        "b_value",
        "etas_p",
        "etas_alpha",
        "ks_p_holm",
    )

    def write(
        self, run: RunDirectory, config: ValidationExperimentConfig, result: EtasBaselineResult
    ) -> None:
        """Write every output into ``run``."""
        config.to_yaml(run.path / "config.resolved.yaml")
        run.write_json(
            "metrics.json", {"pooled": result.pooled, "criterion_met": self._met(result)}
        )
        run.write_frame("per_region.csv", result.per_region, index=True)
        run.write_frame("weekly.csv.gz", result.weekly)
        self._gain_plot(result.per_region, result.pooled, run)
        self._cumulative_plot(result.weekly, run)
        run.write_text("NOTES.md", self._notes(config, result))

    @staticmethod
    def _met(result: EtasBaselineResult) -> bool:
        return bool(result.pooled["info_gain_lo"] > 0)

    def _gain_plot(
        self, per_region: pd.DataFrame, pooled: dict[str, float], run: RunDirectory
    ) -> None:
        table = per_region.sort_values("info_gain_per_event")
        fig = Figure(figsize=(7, max(3.2, 0.35 * len(table) + 1.5)))
        ax = fig.subplots()
        y = np.arange(len(table))
        lo = table["info_gain_per_event"] - table["info_gain_lo"]
        hi = table["info_gain_hi"] - table["info_gain_per_event"]
        ax.errorbar(table["info_gain_per_event"], y, xerr=[lo, hi], fmt="o", color="#2b6cb0")
        ax.axvline(0, color="#555555", linewidth=1)
        ax.axvline(pooled["info_gain_per_event"], color="#999999", linestyle="--", linewidth=1)
        ax.set_yticks(y, table.index)
        ax.set_xlabel(f"information gain, nats per {self.UNIT} (95% block bootstrap)")
        ax.set_title(f"{self.MODEL} vs. {self.REFERENCE}\nvalidation 2020-2025")
        fig.tight_layout()
        fig.savefig(run.path / "info_gain_by_region.png", dpi=110, metadata={"Software": None})

    def _cumulative_plot(self, weekly: pd.DataFrame, run: RunDirectory) -> None:
        diff = weekly.assign(d=weekly["ll_model"] - weekly["ll_reference"])
        totals = pd.DataFrame(diff.groupby("week")[["d", "n"]].sum())
        weeks = pd.to_datetime(totals.index.to_numpy())
        fig = Figure(figsize=(7, 3.2))
        ax = fig.subplots()
        ax.plot(weeks, totals["d"].cumsum().to_numpy(), color="#2b6cb0")
        ax.set_ylabel("cumulative log-likelihood gain, nats")
        ax.set_title(f"{self.MODEL} minus {self.REFERENCE}, all regions, by week")
        fig.tight_layout()
        fig.savefig(run.path / "info_gain_over_time.png", dpi=110, metadata={"Software": None})

    def _bullets(self, pooled: dict[str, float]) -> list[str]:
        return [
            f"- Regions whose time-rescaling KS test rejects (Holm, 0.05): "
            f"{int(pooled['regions_ks_reject_holm_0.05'])}",
            f"- Largest branching ratio: {pooled['max_branching_ratio']:.2f}",
        ]

    def _notes(self, config: ValidationExperimentConfig, result: EtasBaselineResult) -> str:
        pooled, table = result.pooled, result.per_region
        verdict = "MET" if self._met(result) else "NOT MET"
        cols = [c for c in self.COLUMNS if c in table.columns]
        return "\n".join(
            [
                f"# {self.TITLE}",
                "",
                *config.prereg.header(),
                "",
                f"**Primary criterion {verdict}.** Pooled information gain "
                f"{pooled['info_gain_per_event']:.3f} nats/{self.UNIT} "
                f"(95% CI {pooled['info_gain_lo']:.3f} to {pooled['info_gain_hi']:.3f}), "
                f"{int(pooled['n_events'])} scored events in {int(pooled['n_weeks'])} weeks.",
                "",
                f"- Regions with gain CI above 0: {int(pooled['regions_gain_ci_above_0'])} "
                f"of {int(pooled['n_regions'])}",
                *self._bullets(pooled),
                f"- Variants in this family: {config.prereg.variants}",
                "",
                "## Per region",
                "",
                markdown_table(table.loc[:, cols].round(3), index_name="region"),
                "",
            ]
        )
