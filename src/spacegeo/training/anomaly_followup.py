"""Test whether weekly anomaly flags precede large mainshocks.

Pre-registered in docs/experiments/anomaly-followup.md.

Each validation region-week is either flagged by a scan test or not; the
outcome is whether an M >= X mainshock (causal Gardner-Knopoff) occurs in the
same region within the horizon after the week ends. The effect size is the
relative risk, with a moving-block bootstrap over weeks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt
import pandas as pd
from pydantic import Field

from spacegeo.common.geo import GeoRegion
from spacegeo.common.log import get_logger
from spacegeo.common.run import RunDirectory, markdown_table
from spacegeo.common.stats import holm
from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.data.preprocessing.gardner_knopoff import GardnerKnopoffDeclusterer
from spacegeo.data.preprocessing.magnitude_cut import MagnitudeCut
from spacegeo.training.etas_baseline import ValidationExperimentConfig

_log = get_logger(__name__)


class AnomalyFollowupConfig(ValidationExperimentConfig):
    """Config of the flag -> large-mainshock test (``experiment: anomaly_followup``).

    Attributes:
        flags_file: Scan output with ``test``, ``window_start``, ``region``, ``flag``.
        target_magnitude: Smallest target mainshock.
        horizon_days: Days after the flagged week's end (primary).
        secondary_horizon_days: Longer horizon (secondary).
        week_days: Length of a scan window, days.
    """

    experiment: Literal["anomaly_followup"]
    flags_file: Path
    target_magnitude: float = 7.0
    horizon_days: float = Field(default=30.0, gt=0)
    secondary_horizon_days: float = Field(default=60.0, gt=0)
    week_days: float = Field(default=7.0, gt=0)


@dataclass(frozen=True)
class FlagComparison:
    """One flag definition and horizon to compare.

    Attributes:
        name: Label in the outputs.
        tests: Scan tests whose flags count.
        flag: Flag value that counts (``excess`` or ``deficit``).
        horizon_days: Outcome horizon after the week ends.
        primary: Whether this is the pre-registered primary comparison.
    """

    name: str
    tests: tuple[str, ...]
    flag: str
    horizon_days: float
    primary: bool = False


@dataclass(frozen=True)
class AnomalyFollowupResult:
    """Run outputs.

    Attributes:
        comparisons: One row per comparison: 2x2 counts, RR with interval, p-values, Brier skill.
        base_rates: Share of region-weeks with a target, for training and validation.
        targets: The target mainshocks in the validation span.
    """

    comparisons: pd.DataFrame
    base_rates: pd.DataFrame
    targets: pd.DataFrame


class AnomalyFollowupExperiment:
    """Runs the pre-registered comparisons.

    Args:
        config: Experiment config.
        regions: Region name -> geometry (must match the scan's regions).
        catalog: M >= mc catalog from ``history_start`` on; events at or after
            ``val_end`` are dropped, so no outcome reaches into the test span.
    """

    def __init__(
        self, config: AnomalyFollowupConfig, regions: dict[str, GeoRegion], catalog: pd.DataFrame
    ) -> None:
        self._config = config
        self._regions = regions
        self._catalog = catalog.loc[catalog.index < to_utc(config.val_end)]

    def comparisons(self) -> tuple[FlagComparison, ...]:
        """Primary first, then the three pre-registered secondaries."""
        c = self._config
        return (
            FlagComparison(
                "mainshocks_excess_30d", ("mainshocks",), "excess", c.horizon_days, True
            ),
            FlagComparison("activity_excess_30d", ("activity",), "excess", c.horizon_days),
            FlagComparison(
                "any_deficit_30d", ("activity", "mainshocks"), "deficit", c.horizon_days
            ),
            FlagComparison(
                "mainshocks_excess_60d", ("mainshocks",), "excess", c.secondary_horizon_days
            ),
        )

    def run(self) -> AnomalyFollowupResult:
        """Build outcomes, compare, summarize."""
        targets = self._targets()
        flags = self._flags()
        rows = [self._compare(cmp, flags, targets) for cmp in self.comparisons()]
        table = pd.DataFrame(rows)
        secondary = ~table["primary"].to_numpy(dtype=bool)
        holm_p = np.full(len(table), np.nan)
        holm_p[secondary] = holm(table.loc[secondary, "p_rr_le_1"].to_numpy(dtype=np.float64))
        table["p_holm_secondary"] = holm_p
        val_targets = targets.loc[self._config.validation.mask(targets.index)]
        return AnomalyFollowupResult(
            comparisons=table, base_rates=self._base_rates(targets), targets=val_targets
        )

    def _targets(self) -> pd.DataFrame:
        cut = MagnitudeCut(self._config.mc).transform(self._catalog)
        mainshocks = GardnerKnopoffDeclusterer(include_foreshocks=False).transform(cut)
        big = mainshocks.loc[mainshocks["mag"] >= self._config.target_magnitude - 1e-9]
        region = pd.Series("", index=big.index, dtype=object)
        for name, geo in self._regions.items():
            region[geo.contains(big["lat_deg"], big["lon_deg"])] = name
        out = big.assign(region=region.to_numpy())
        return out.loc[out["region"] != ""]

    def _flags(self) -> pd.DataFrame:
        flags = pd.read_csv(self._config.flags_file)
        flags["flag"] = flags["flag"].fillna("").astype(str)
        flags["window_start"] = pd.to_datetime(flags["window_start"], utc=True)
        unknown = set(flags["region"]) - set(self._regions)
        if unknown:
            raise ValueError(f"Scan regions not in the regions file: {sorted(unknown)}")
        return flags

    def _outcomes(
        self, weeks: pd.DataFrame, targets: pd.DataFrame, horizon_days: float
    ) -> npt.NDArray[np.int64]:
        week_end = weeks["window_start"] + duration(days=self._config.week_days)
        out = np.zeros(len(weeks), dtype=np.int64)
        for name, group in targets.groupby("region"):
            times = pd.DatetimeIndex(group.index)
            rows = np.flatnonzero(weeks["region"].to_numpy() == name)
            for i in rows:
                window = TimeWindow(
                    week_end.iloc[i], week_end.iloc[i] + duration(days=horizon_days)
                )
                out[i] = int(window.mask(times).any())
        return out

    def _units(self, flags: pd.DataFrame, cmp: FlagComparison) -> pd.DataFrame:
        relevant = flags.loc[flags["test"].isin(cmp.tests)]
        flagged = relevant.assign(hit=relevant["flag"] == cmp.flag)
        units = pd.DataFrame(
            flagged.groupby(["window_start", "region"], as_index=False)["hit"].any()
        )
        last_end = to_utc(self._config.val_end) - duration(
            days=self._config.week_days + cmp.horizon_days
        )
        starts = pd.DatetimeIndex(pd.to_datetime(units["window_start"], utc=True))
        return units.loc[np.asarray(starts <= last_end)].reset_index(drop=True)

    def _compare(
        self, cmp: FlagComparison, flags: pd.DataFrame, targets: pd.DataFrame
    ) -> dict[str, object]:
        units = self._units(flags, cmp)
        y = self._outcomes(units, targets, cmp.horizon_days)
        hit = units["hit"].to_numpy(dtype=bool)
        week = pd.factorize(units["window_start"])[0]
        a, b = int(y[hit].sum()), int(hit.sum())
        c, d = int(y[~hit].sum()), int((~hit).sum())
        rr = _relative_risk(a, b, c, d)
        samples = self._bootstrap(week, hit, y)
        low, high = (
            np.nanpercentile(samples, [2.5, 97.5]) if np.isfinite(samples).any() else (np.nan,) * 2
        )
        return {
            "comparison": cmp.name,
            "primary": cmp.primary,
            "flagged_weeks": b,
            "flagged_with_target": a,
            "unflagged_weeks": d,
            "unflagged_with_target": c,
            "p_target_given_flag": a / b if b else np.nan,
            "p_target_given_no_flag": c / d if d else np.nan,
            "relative_risk": rr,
            "rr_lo": float(low),
            "rr_hi": float(high),
            "p_rr_le_1": float(np.mean(~(samples > 1))),
            "resamples_without_flags": float(np.mean(~np.isfinite(samples))),
            "brier_skill_vs_base_rate": _brier_skill(hit, y),
        }

    def _bootstrap(
        self, week: npt.NDArray[np.int64], hit: npt.NDArray[np.bool_], y: npt.NDArray[np.int64]
    ) -> npt.NDArray[np.float64]:
        n_weeks = int(week.max()) + 1
        sums = [
            np.bincount(week, weights=w.astype(np.float64), minlength=n_weeks)
            for w in (hit & (y == 1), hit, ~hit & (y == 1), ~hit)
        ]
        idx = self._config.bootstrap_indices(n_weeks)
        a, b, c, d = (s[idx].sum(axis=1) for s in sums)
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where((b > 0) & (c > 0), (a / b) / (c / d), np.nan)

    def _base_rates(self, targets: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for label, span in (("train", self._config.train), ("validation", self._config.validation)):
            weeks = self._config.weeks_between(span.start.to_pydatetime(), span.end.to_pydatetime())
            last = span.end - duration(days=self._config.horizon_days)
            starts = [w.start for w in weeks if w.end <= last]
            grid = pd.DataFrame(
                [(s, r) for s in starts for r in self._regions], columns=["window_start", "region"]
            )
            y = self._outcomes(grid, targets, self._config.horizon_days)
            rows.append({"span": label, "region_weeks": len(grid), "base_rate": float(y.mean())})
        return pd.DataFrame(rows)


def _relative_risk(a: int, b: int, c: int, d: int) -> float:
    if b == 0 or d == 0 or c == 0:
        return float("nan")
    return (a / b) / (c / d)


def _brier_skill(hit: npt.NDArray[np.bool_], y: npt.NDArray[np.int64]) -> float:
    """In-sample two-level forecast (rate given flag / given no flag) vs. the base rate."""
    base = float(y.mean())
    if base in (0.0, 1.0):
        return float("nan")
    p = np.where(hit, y[hit].mean() if hit.any() else base, y[~hit].mean())
    return 1 - float(((p - y) ** 2).mean()) / float(((base - y) ** 2).mean())


class AnomalyFollowupReport:
    """Writes the follow-up run: tables, metrics and NOTES.md."""

    def write(
        self, run: RunDirectory, config: AnomalyFollowupConfig, result: AnomalyFollowupResult
    ) -> None:
        """Write every output into ``run``."""
        config.to_yaml(run.path / "config.resolved.yaml")
        primary = result.comparisons.loc[result.comparisons["primary"].to_numpy(dtype=bool)]
        record = {str(k): v for k, v in primary.to_dict("records")[0].items()}
        run.write_json(
            "metrics.json",
            {"criterion_met": self.met(result), "primary": _jsonable(record)},
        )
        run.write_frame("comparisons.csv", result.comparisons)
        run.write_frame("base_rates.csv", result.base_rates)
        run.write_frame("targets.csv", result.targets, index=True)
        run.write_text("NOTES.md", self._notes(config, result, record))

    @staticmethod
    def met(result: AnomalyFollowupResult) -> bool:
        """Pre-registered criterion: lower bound of the primary RR interval > 1."""
        table = result.comparisons
        low = table.loc[table["primary"].to_numpy(dtype=bool), "rr_lo"].to_numpy(dtype=np.float64)
        return bool(np.isfinite(low[0]) and low[0] > 1)

    def _notes(
        self,
        config: AnomalyFollowupConfig,
        result: AnomalyFollowupResult,
        primary: dict[str, object],
    ) -> str:
        verdict = "MET" if self.met(result) else "NOT MET"
        return "\n".join(
            [
                "# Do anomaly flags precede M>=7 mainshocks?",
                "",
                *config.prereg.header(),
                "",
                f"**Primary criterion {verdict}.** Mainshocks-excess flags: relative risk "
                f"{_fmt(primary['relative_risk'])} (95% CI {_fmt(primary['rr_lo'])} to "
                f"{_fmt(primary['rr_hi'])}); {primary['flagged_with_target']} of "
                f"{primary['flagged_weeks']} flagged region-weeks vs. "
                f"{primary['unflagged_with_target']} of {primary['unflagged_weeks']} "
                "unflagged were followed by a target.",
                "",
                "## All comparisons",
                "",
                markdown_table(result.comparisons),
                "",
                "## Base rate of the target",
                "",
                markdown_table(result.base_rates),
                "",
                f"## Validation targets ({len(result.targets)})",
                "",
                markdown_table(
                    result.targets.loc[:, ["region", "mag", "lat_deg", "lon_deg"]],
                    index_name="time",
                ),
                "",
            ]
        )


def _fmt(value: object) -> str:
    number = float(str(value))
    return "n/a" if not np.isfinite(number) else f"{number:.2f}"


def _jsonable(record: dict[str, object]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in record.items():
        if isinstance(value, bool | np.bool_):
            out[key] = bool(value)
        elif isinstance(value, int | np.integer):
            out[key] = int(value)
        elif isinstance(value, float | np.floating):
            out[key] = float(value) if np.isfinite(value) else None
        else:
            out[key] = str(value)
    return out
