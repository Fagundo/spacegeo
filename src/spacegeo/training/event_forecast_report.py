"""Write a weekly event-forecast run: tables, metrics, plots and NOTES.md."""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from spacegeo.common.run import RunDirectory, markdown_table
from spacegeo.training.event_forecast import (
    REFERENCE,
    EventForecastConfig,
    EventForecastResult,
)

_MODEL = "gradient_boosting"


class EventForecastReport:
    """Turns an :class:`EventForecastResult` into run-directory files."""

    def write(
        self, run: RunDirectory, config: EventForecastConfig, result: EventForecastResult
    ) -> None:
        """Write every output into ``run``."""
        config.to_yaml(run.path / "config.resolved.yaml")
        primary = self._primary(result.scores)
        run.write_json(
            "metrics.json",
            {
                "criterion_met": self.met(result),
                "primary": {k: v for k, v in primary.items() if k not in ("target", "model")},
            },
        )
        run.write_frame("scores.csv", result.scores)
        run.write_frame("reliability.csv", result.reliability)
        run.write_frame("importance.csv", result.importance)
        run.write_frame("predictions.csv.gz", result.predictions)
        self._gain_plot(result.scores, run)
        self._reliability_plot(result.reliability, run)
        run.write_text("NOTES.md", self._notes(config, result))

    @staticmethod
    def _primary(scores: pd.DataFrame) -> dict[str, object]:
        rows = scores.loc[(scores["target"] == "y_primary") & (scores["model"] == _MODEL)]
        return {str(k): v for k, v in rows.iloc[0].to_dict().items()}

    def met(self, result: EventForecastResult) -> bool:
        """Whether the pre-registered primary criterion holds."""
        low = self._primary(result.scores)[f"gain_vs_{REFERENCE}_lo"]
        return bool(float(str(low)) > 0)

    @staticmethod
    def _gain_plot(scores: pd.DataFrame, run: RunDirectory) -> None:
        table = scores.loc[scores["target"] == "y_primary"].set_index("model")
        order = ["climatology", "etas_raw", REFERENCE, _MODEL]
        table = table.loc[[m for m in order if m in table.index]]
        fig = Figure(figsize=(7, 3.2))
        ax = fig.subplots()
        y = np.arange(len(table))
        mid = table["gain_vs_climatology"].to_numpy()
        err = [
            mid - table["gain_vs_climatology_lo"].to_numpy(),
            table["gain_vs_climatology_hi"].to_numpy() - mid,
        ]
        ax.errorbar(mid, y, xerr=err, fmt="o", color="#2b6cb0")
        ax.axvline(0, color="#555555", linewidth=1)
        ax.set_yticks(y, list(table.index))
        ax.set_xlabel("gain over climatology, nats per region-week (95% block bootstrap)")
        ax.set_title("Forecasting M>=6 next week, validation 2020-2025")
        fig.tight_layout()
        fig.savefig(run.path / "gain_by_model.png", dpi=110, metadata={"Software": None})

    @staticmethod
    def _reliability_plot(reliability: pd.DataFrame, run: RunDirectory) -> None:
        fig = Figure(figsize=(4.6, 4.2))
        ax = fig.subplots()
        for model, table in reliability.groupby("model", sort=True):
            ax.plot(
                table["mean_predicted"].to_numpy(),
                table["observed_frequency"].to_numpy(),
                marker="o",
                label=str(model),
            )
        top = float(reliability[["mean_predicted", "observed_frequency"]].to_numpy().max())
        ax.plot([0, top], [0, top], color="#999999", linestyle="--", linewidth=1)
        ax.set_xlabel("predicted probability (decile mean)")
        ax.set_ylabel("observed frequency")
        ax.set_title("Reliability, M>=6 next week")
        ax.legend(frameon=False, fontsize=8)
        fig.tight_layout()
        fig.savefig(run.path / "reliability.png", dpi=110, metadata={"Software": None})

    def _notes(self, config: EventForecastConfig, result: EventForecastResult) -> str:
        p = self._primary(result.scores)
        verdict = "MET" if self.met(result) else "NOT MET"
        cols = [
            "target",
            "model",
            "mean_log_score",
            f"gain_vs_{REFERENCE}",
            f"gain_vs_{REFERENCE}_lo",
            f"gain_vs_{REFERENCE}_hi",
            "gain_vs_climatology",
            "brier_skill_vs_climatology",
            "roc_auc",
            "base_rate",
        ]
        return "\n".join(
            [
                "# Weekly M>=6 forecast: gradient boosting vs. ETAS",
                "",
                *config.prereg.header(),
                "",
                f"**Primary criterion {verdict}.** Gain of gradient boosting over "
                f"ETAS-recalibrated: {float(str(p[f'gain_vs_{REFERENCE}'])):.4f} nats per "
                f"region-week (95% CI {float(str(p[f'gain_vs_{REFERENCE}_lo'])):.4f} to "
                f"{float(str(p[f'gain_vs_{REFERENCE}_hi'])):.4f}); base rate "
                f"{float(str(p['base_rate'])):.3f}, {len(result.predictions)} validation "
                "region-weeks.",
                "",
                "## Scores",
                "",
                markdown_table(result.scores.loc[:, cols]),
                "",
                "## Permutation importance (gradient boosting, validation)",
                "",
                markdown_table(result.importance.head(12)),
                "",
            ]
        )
