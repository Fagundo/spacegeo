"""Write an ETAS baseline run: tables, metrics, plots and NOTES.md."""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from spacegeo.common.run import RunDirectory
from spacegeo.training.etas_baseline import EtasBaselineResult, EtasExperimentConfig


class EtasBaselineReport:
    """Turns an :class:`EtasBaselineResult` into run-directory files."""

    def write(
        self, run: RunDirectory, config: EtasExperimentConfig, result: EtasBaselineResult
    ) -> None:
        """Write every output into ``run``."""
        config.to_yaml(run.path / "config.resolved.yaml")
        run.write_json(
            "metrics.json", {"pooled": result.pooled, "criterion_met": self._met(result)}
        )
        result.per_region.to_csv(run.path / "per_region.csv", float_format="%.6g")
        result.weekly.to_csv(
            run.path / "weekly.csv.gz",
            index=False,
            float_format="%.6g",
            compression={"method": "gzip", "mtime": 0},
        )
        self._gain_plot(result.per_region, result.pooled, run)
        self._cumulative_plot(result.weekly, run)
        run.write_text("NOTES.md", self._notes(config, result))

    @staticmethod
    def _met(result: EtasBaselineResult) -> bool:
        return bool(result.pooled["info_gain_lo"] > 0)

    @staticmethod
    def _gain_plot(per_region: pd.DataFrame, pooled: dict[str, float], run: RunDirectory) -> None:
        table = per_region.sort_values("info_gain_per_event")
        fig = Figure(figsize=(7, 6))
        ax = fig.subplots()
        y = np.arange(len(table))
        lo = table["info_gain_per_event"] - table["info_gain_lo"]
        hi = table["info_gain_hi"] - table["info_gain_per_event"]
        ax.errorbar(table["info_gain_per_event"], y, xerr=[lo, hi], fmt="o", color="#2b6cb0")
        ax.axvline(0, color="#555555", linewidth=1)
        ax.axvline(pooled["info_gain_per_event"], color="#999999", linestyle="--", linewidth=1)
        ax.set_yticks(y, table.index)
        ax.set_xlabel("information gain of ETAS over smoothed Poisson, nats per event")
        ax.set_title("Validation 2020-2025: ETAS vs. smoothed Poisson (95% block bootstrap)")
        fig.tight_layout()
        fig.savefig(run.path / "info_gain_by_region.png", dpi=110, metadata={"Software": None})

    @staticmethod
    def _cumulative_plot(weekly: pd.DataFrame, run: RunDirectory) -> None:
        diff = weekly.assign(d=weekly["ll_etas"] - weekly["ll_poisson"])
        totals = pd.DataFrame(diff.groupby("week")[["d", "n"]].sum())
        weeks = pd.to_datetime(totals.index.to_numpy())
        fig = Figure(figsize=(7, 3.2))
        ax = fig.subplots()
        ax.plot(weeks, totals["d"].cumsum().to_numpy(), color="#2b6cb0")
        ax.set_ylabel("cumulative log-likelihood gain, nats")
        ax.set_title("ETAS minus smoothed Poisson, all regions, by week")
        fig.tight_layout()
        fig.savefig(run.path / "info_gain_over_time.png", dpi=110, metadata={"Software": None})

    def _notes(self, config: EtasExperimentConfig, result: EtasBaselineResult) -> str:
        pooled, table = result.pooled, result.per_region
        verdict = "MET" if self._met(result) else "NOT MET"
        cols = [
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
        ]
        return "\n".join(
            [
                "# ETAS baseline, Ring of Fire",
                "",
                f"Hypothesis: {config.prereg.hypothesis}",
                f"Success criterion: {config.prereg.success}",
                "",
                f"**Primary criterion {verdict}.** Pooled information gain "
                f"{pooled['info_gain_per_event']:.3f} nats/event "
                f"(95% CI {pooled['info_gain_lo']:.3f} to {pooled['info_gain_hi']:.3f}), "
                f"{int(pooled['n_events'])} validation events in {int(pooled['n_weeks'])} weeks.",
                "",
                f"- Regions with gain CI above 0: {int(pooled['regions_gain_ci_above_0'])} "
                f"of {int(pooled['n_regions'])}",
                f"- Regions whose time-rescaling KS test rejects (Holm, 0.05): "
                f"{int(pooled['regions_ks_reject_holm_0.05'])}",
                f"- Largest branching ratio: {pooled['max_branching_ratio']:.2f}",
                f"- Variants in this family: {config.prereg.variants}",
                "",
                "## Per region",
                "",
                _markdown(table.loc[:, cols].round(3)),
                "",
            ]
        )


def _markdown(frame: pd.DataFrame) -> str:
    header = "| region | " + " | ".join(str(c) for c in frame.columns) + " |"
    rule = "|" + "---|" * (len(frame.columns) + 1)
    rows = [
        "| " + " | ".join([str(name), *(f"{v:g}" for v in row)]) + " |"
        for name, row in zip(frame.index, frame.to_numpy(dtype=np.float64), strict=True)
    ]
    return "\n".join([header, rule, *rows])
