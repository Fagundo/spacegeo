"""Write scan results to the committed ``results/anomaly`` tree."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from spacegeo.common.time import duration
from spacegeo.evaluation.anomaly import RESULT_COLUMNS
from spacegeo.monitoring.plots import ValidationPlots
from spacegeo.monitoring.validation import ValidationReport

_FLOAT = "%.6g"
_HIDDEN_IN_TABLES = frozenset({"ratio", "log_score", "pit"})
_TABLE_COLUMNS = ["region", *(c for c in RESULT_COLUMNS if c not in _HIDDEN_IN_TABLES)]


class ScanReportWriter:
    """Deterministic CSV / Markdown outputs (no wall-clock timestamps).

    Re-running on unchanged data rewrites identical files, so the weekly CI
    only commits when the catalog or the scan actually changed.

    Args:
        root: Output directory, e.g. ``results/anomaly``.
    """

    def __init__(self, root: Path, plots: ValidationPlots | None = None) -> None:
        self._root = root
        self._plots = plots or ValidationPlots()

    @property
    def validation_dir(self) -> Path:
        """Validation outputs."""
        return self._root / "validation"

    @property
    def test_dir(self) -> Path:
        """Live test-period outputs."""
        return self._root / "test"

    def write_validation(self, report: ValidationReport) -> None:
        """Store validation weeks, calibration, model comparison and power."""
        out = self.validation_dir
        out.mkdir(parents=True, exist_ok=True)
        self._csv(report.results, out / "weekly.csv.gz", index=False)
        self._csv(report.by_test, out / "by_test.csv")
        self._csv(report.by_region, out / "by_region.csv")
        self._csv(report.pit_histogram, out / "pit_histogram.csv", index=False)
        self._csv(report.model_comparison, out / "model_comparison.csv")
        self._csv(report.power, out / "power.csv", index=False)
        self._csv(report.min_detectable, out / "min_detectable.csv", index=False)
        self._plots.pit(report.pit_histogram, out / "pit.png")
        self._plots.power(report.power, out / "power.png")
        (out / "README.md").write_text(self._validation_markdown(report))

    def _validation_markdown(self, report: ValidationReport) -> str:
        comparison = report.model_comparison.reset_index()
        detectable = report.min_detectable.pivot(
            index="region", columns="test", values="min_detectable_added"
        )
        lines = [
            "# Validation (train fit, validation weeks scored)",
            "",
            "Pre-registration: `docs/experiments/anomaly-scan.md`.",
            "",
            "## Calibration of the live tests",
            "",
            self._frame_table(report.by_test.reset_index()),
            "",
            "![PIT histogram](pit.png)",
            "",
            "## Model comparison",
            "",
            "Mean log score per region-week; information gain vs. Poisson; 95% intervals",
            "from a 13-week moving-block bootstrap.",
            "",
            self._frame_table(comparison),
            "",
            "## Detection power (injected extra events in one region-week)",
            "",
            "![Power curve](power.png)",
            "",
            "Smallest burst flagged in at least 80% of validation weeks",
            "(blank: never at the tested sizes):",
            "",
            self._frame_table(detectable.reset_index()),
        ]
        return "\n".join(lines) + "\n"

    @staticmethod
    def _frame_table(frame: pd.DataFrame) -> str:
        columns = [str(c) for c in frame.columns]
        header = "| " + " | ".join(columns) + " |"
        rule = "|" + "---|" * len(columns)
        rows = [
            "| " + " | ".join(_cell(v) for v in row) + " |" for row in frame.itertuples(index=False)
        ]
        return "\n".join([header, rule, *rows])

    def write_predictions(self, results: pd.DataFrame, calibration: pd.DataFrame | None) -> None:
        """Store every test week and a Markdown summary of the latest one."""
        out = self.test_dir
        out.mkdir(parents=True, exist_ok=True)
        self._csv(results, out / "weekly.csv", index=False)
        (out / "latest.md").write_text(self._markdown(results, calibration))

    @staticmethod
    def _csv(frame: pd.DataFrame, path: Path, *, index: bool = True) -> None:
        compression = {"method": "gzip", "mtime": 0} if path.suffix == ".gz" else None
        frame.to_csv(
            path, index=index, float_format=_FLOAT, lineterminator="\n", compression=compression
        )

    def _markdown(self, results: pd.DataFrame, calibration: pd.DataFrame | None) -> str:
        latest_start = results["window_start"].max()
        latest = results.loc[results["window_start"] == latest_start]
        latest_end = latest_start + duration(days=7)
        flagged = results.loc[results["flag"] != ""]
        lines = [
            "# Ring of Fire weekly anomaly scan",
            "",
            f"Latest week: {latest_start:%Y-%m-%d} to {latest_end:%Y-%m-%d} (UTC, end exclusive).",
            "Models fit on the training + validation span. `flag` = q <= FDR within the week.",
            "Recent days are preliminary: USGS adds and revises events for weeks.",
            "",
            *self._calibration_lines(calibration),
        ]
        for test, table in latest.groupby("test", sort=True):
            lines += ["", f"## {test}", "", self._md_table(table.sort_values(["p_high", "p_low"]))]
        lines += ["", "## All flagged region-weeks in the test period", ""]
        lines.append(self._md_table(flagged, with_week=True) if len(flagged) else "None.")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _calibration_lines(calibration: pd.DataFrame | None) -> list[str]:
        if calibration is None:
            return ["Validation not run yet."]
        verdicts = ", ".join(
            f"{test}: {'calibrated' if bool(ok) else 'NOT calibrated'}"
            for test, ok in calibration["calibrated"].items()
        )
        return [f"Validation verdict: {verdicts}. See `../validation/by_test.csv`."]

    def _md_table(self, table: pd.DataFrame, *, with_week: bool = False) -> str:
        wanted = (["window_start", "test"] if with_week else []) + _TABLE_COLUMNS
        columns = [c for c in wanted if c in table.columns]
        frame = table.loc[:, columns].copy()
        if with_week:
            frame["window_start"] = pd.to_datetime(frame["window_start"]).dt.strftime("%Y-%m-%d")
        return self._frame_table(frame)


def _cell(value: object) -> str:
    if isinstance(value, float):
        return "" if math.isnan(value) else f"{value:.3g}"
    return str(value)
