"""Write the ETAS + space-weather run: tables, metrics, plots and NOTES.md."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from spacegeo.common.run import RunDirectory, markdown_table
from spacegeo.training.space_weather_etas import (
    SpaceWeatherEtasConfig,
    SpaceWeatherEtasResult,
)

_MARK = "#2b6cb0"
_REFERENCE = "#555555"
_TAU = re.compile(r"_logratio_([0-9.]+)d_vs_")


class SpaceWeatherEtasReport:
    """Turns a :class:`SpaceWeatherEtasResult` into run-directory files."""

    def write(
        self, run: RunDirectory, config: SpaceWeatherEtasConfig, result: SpaceWeatherEtasResult
    ) -> None:
        """Write every output into ``run``."""
        config.to_yaml(run.path / "config.resolved.yaml")
        table = result.variants
        run.write_json(
            "metrics.json",
            {
                "variants": table.reset_index().to_dict("records"),
                "any_detected": bool(table["detected"].any()),
                "missing_covariate_hours": result.missing,
            },
        )
        run.write_frame("variants.csv", table, index=True)
        run.write_frame("per_region.csv", result.per_region, index=True)
        run.write_frame("weekly.csv.gz", result.weekly)
        run.write_frame("shift_null.csv", pd.DataFrame(result.shift_null))
        self._response_plot(table, run)
        self._shift_plot(table, result.shift_null, run)
        run.write_text("NOTES.md", self._notes(config, result))

    @staticmethod
    def _response(table: pd.DataFrame, variant: str) -> pd.DataFrame:
        """Rate change per 1 sd and its interval, one row per smoothing scale."""
        row = table.loc[variant]
        rows = []
        for key in table.columns:
            match = _TAU.search(key) if key.startswith("rate_change_pct[") else None
            if match:
                name = key[len("rate_change_pct[") : -1]
                rows.append(
                    {
                        "driver": name.split("_logratio_")[0],
                        "tau_days": float(match.group(1)),
                        "pct": row[key],
                        "lo": row[f"rate_change_lo[{name}]"],
                        "hi": row[f"rate_change_hi[{name}]"],
                    }
                )
        frame = pd.DataFrame(rows).dropna()
        return frame.sort_values(["driver", "tau_days"]) if len(frame) else frame

    def _response_plot(self, table: pd.DataFrame, run: RunDirectory) -> None:
        primary = [v for v in table.index if bool(table.loc[v, "primary"])]
        fig = Figure(figsize=(3.2 * len(primary), 3.2))
        axes = np.atleast_1d(fig.subplots(1, len(primary), sharey=True))
        for ax, variant in zip(axes, primary, strict=True):
            r = self._response(table, variant)
            yerr = np.maximum([r["pct"] - r["lo"], r["hi"] - r["pct"]], 0.0)
            ax.errorbar(r["tau_days"], r["pct"], yerr=yerr, fmt="o-", color=_MARK, linewidth=1.5)
            ax.axhline(0, color=_REFERENCE, linewidth=1)
            ax.set_xscale("log")
            ax.minorticks_off()
            ax.set_xticks(r["tau_days"], [f"{t:g} d" for t in r["tau_days"]])
            ax.set_title(str(variant))
            ax.set_xlabel("smoothing scale")
        axes[0].set_ylabel("background rate change per 1 sd, %\n(95% block bootstrap)")
        fig.suptitle("Fitted background response by time scale (training fit)")
        fig.tight_layout()
        fig.savefig(run.path / "response_by_scale.png", dpi=110, metadata={"Software": None})

    @staticmethod
    def _shift_plot(table: pd.DataFrame, null: dict[str, np.ndarray], run: RunDirectory) -> None:
        if not null:
            return
        fig = Figure(figsize=(3.2 * len(null), 3.0))
        axes = np.atleast_1d(fig.subplots(1, len(null), sharey=True))
        for ax, (variant, gains) in zip(axes, null.items(), strict=True):
            ax.hist(gains, bins=25, color="#9fb7d6", edgecolor="white", linewidth=1)
            ax.axvline(table.loc[variant, "info_gain_per_event"], color=_MARK, linewidth=2)
            ax.set_title(f"{variant} (p = {table.loc[variant, 'p_shift']:.3f})")
            ax.set_xlabel("validation gain, nats/event")
        axes[0].set_ylabel("circular shifts")
        fig.suptitle("Observed gain (line) vs. shifted space weather (bars)")
        fig.tight_layout()
        fig.savefig(run.path / "shift_test.png", dpi=110, metadata={"Software": None})

    def _notes(self, config: SpaceWeatherEtasConfig, result: SpaceWeatherEtasResult) -> str:
        table = result.variants
        detected = [str(v) for v in table.index if bool(table.loc[v, "detected"])]
        verdict = (
            f"**Detected: {', '.join(detected)}.**"
            if detected
            else "**No mechanism detected (null).** The pre-registered criterion is not met."
        )
        cols = [
            "info_gain_per_event",
            "info_gain_lo",
            "info_gain_hi",
            "p_shift",
            "p_shift_holm",
            "detected",
            "maglat_spearman_rho",
            "maglat_spearman_p",
        ]
        return "\n".join(
            [
                "# ETAS + space-weather background, Ring of Fire",
                "",
                *config.prereg.header(),
                "",
                verdict,
                "",
                f"## Variants (gain in nats/event over ETAS, validation "
                f"{config.val_start:%Y-%m-%d} to {config.val_end:%Y-%m-%d})",
                "",
                markdown_table(table.loc[:, cols].round(4), index_name="variant"),
                "",
                "## Rate change per 1 sd of each covariate (training fit, 95% interval)",
                "",
                "Each value holds the other scales fixed. The scales are correlated, so",
                "single coefficients can be large with opposite signs; the sustained",
                "change (all scales of a variant up 1 sd together) is the stabler summary.",
                "",
                *self._response_lines(table),
                "",
                "## Notes",
                "",
                f"- Variants in this family: {config.prereg.variants} "
                f"(primary: {int(table['primary'].to_numpy(dtype=bool).sum())}, Holm across them).",
                "- Shift test wraps the hourly grid from the end of the ETAS burn-in "
                f"({config.fit_window.start:%Y-%m-%d}) to {config.val_end:%Y-%m-%d}.",
                f"- Beta intervals: {result.beta_resamples} refits on moving-block "
                "resamples of 7-day blocks of the fit span.",
                "- Missing covariate hours (set to 0): "
                + ", ".join(f"{k} {v:.1%}" for k, v in result.missing.items()),
                "",
                "## Per region",
                "",
                markdown_table(result.per_region.round(4), index_name="region"),
                "",
            ]
        )

    def _response_lines(self, table: pd.DataFrame) -> list[str]:
        lines = []
        for variant in table.index:
            r = self._response(table, str(variant))
            parts = [
                f"{d} {t:g} d {p:+.1f}% [{lo:+.1f}, {hi:+.1f}]"
                for d, t, p, lo, hi in r.itertuples(index=False)
            ]
            row = table.loc[variant]
            sustained = (
                f"sustained {row['sustained_change_pct']:+.1f}% "
                f"[{row['sustained_change_lo']:+.1f}, {row['sustained_change_hi']:+.1f}]"
            )
            lines.append(f"- {variant}: {sustained}; " + "; ".join(parts))
        return lines
