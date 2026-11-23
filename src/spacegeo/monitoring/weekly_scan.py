"""Weekly anomaly scan over the validation span and the live test span."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

import pandas as pd

from spacegeo.common.log import get_logger
from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.data.preprocessing.gardner_knopoff import GardnerKnopoffDeclusterer
from spacegeo.data.preprocessing.magnitude_cut import MagnitudeCut
from spacegeo.evaluation.anomaly import RegionalAnomalyScanner
from spacegeo.models.base import CountModel
from spacegeo.models.count import EmpiricalCountModel, PoissonCountModel
from spacegeo.monitoring.config import WeeklyScanConfig

_log = get_logger(__name__)


@dataclass(frozen=True)
class ScanRun:
    """Results of one scan plus the fitted scanners that produced them.

    Attributes:
        results: Long frame, one row per test x window x region.
        scanners: Fitted scanner per test name.
    """

    results: pd.DataFrame
    scanners: Mapping[str, RegionalAnomalyScanner]


@dataclass(frozen=True)
class ScanTest:
    """One named test: a catalog variant and the count model applied to it.

    Attributes:
        name: Label used in outputs (``activity``, ``mainshocks``).
        events: Catalog the test counts.
        model_factory: Builds a fresh count model.
    """

    name: str
    events: pd.DataFrame
    model_factory: Callable[[], CountModel]


class WeeklyAnomalyScan:
    """Runs every :class:`ScanTest` over weekly windows.

    The default tests are:

    * ``activity``: the Mc-cut catalog against the empirical distribution of
      historical weekly counts (heavy aftershock tails included as observed).
      A negative binomial was tried first and failed calibration on
      simulated clustered data; see ``docs/experiments/anomaly-scan.md``.
    * ``mainshocks``: the catalog declustered with causal Gardner-Knopoff
      windows (aftershocks only, so a week never depends on later events)
      against a Poisson rate.

    Args:
        config: Regions, cut and split.
        catalog: Parsed catalog (``lat_deg``, ``lon_deg``, ``mag``; UTC index).
        tests: Override the default tests.
    """

    def __init__(
        self,
        config: WeeklyScanConfig,
        catalog: pd.DataFrame,
        tests: tuple[ScanTest, ...] | None = None,
    ) -> None:
        self._config = config
        self._tests = tests or self._default_tests(
            config, MagnitudeCut(config.mc).transform(catalog)
        )

    @property
    def tests(self) -> tuple[ScanTest, ...]:
        """The tests this scan runs."""
        return self._tests

    @staticmethod
    def _default_tests(config: WeeklyScanConfig, cut: pd.DataFrame) -> tuple[ScanTest, ...]:
        horizon = duration(days=config.horizon_days)
        mainshocks = GardnerKnopoffDeclusterer(include_foreshocks=False).transform(cut)
        return (
            ScanTest("activity", cut, lambda: EmpiricalCountModel(horizon)),
            ScanTest("mainshocks", mainshocks, lambda: PoissonCountModel(horizon)),
        )

    def weeks(self, span: TimeWindow) -> list[TimeWindow]:
        """Whole anchored windows that fit inside ``span``."""
        horizon = duration(days=self._config.horizon_days)
        starts = pd.date_range(span.start, span.end, freq=self._config.week_anchor)
        return [TimeWindow(s, s + horizon) for s in starts if s + horizon <= span.end]

    def validation_weeks(self) -> list[TimeWindow]:
        """Validation windows, starting after the gap."""
        span = self._config.validation
        return self.weeks(TimeWindow(span.start + self._config.gap, span.end))

    def validate(self) -> ScanRun:
        """Fit on the training span and score every validation week after the gap."""
        return self._run(self._config.train, self.validation_weeks())

    def predict(self, as_of: pd.Timestamp) -> ScanRun:
        """Fit on train + validation; score complete test weeks after the gap, before ``as_of``."""
        stop = to_utc(as_of)
        start = to_utc(self._config.test_start) + self._config.gap
        if stop <= start:
            raise ValueError(f"as_of {stop} is not after the first test week start {start}.")
        return self._run(self._config.refit, self.weeks(TimeWindow(start, stop)))

    def _run(self, fit_window: TimeWindow, weeks: list[TimeWindow]) -> ScanRun:
        if not weeks:
            raise ValueError("No complete weeks to score.")
        tables = []
        scanners: dict[str, RegionalAnomalyScanner] = {}
        for test in self._tests:
            scanner = RegionalAnomalyScanner(
                self._config.regions, test.model_factory, self._config.fdr
            )
            table = scanner.fit(test.events, fit_window).score(test.events, weeks)
            scanners[test.name] = scanner
            table.insert(0, "test", test.name)
            tables.append(table)
            _log.info(
                "%s: scored %d weeks x %d regions", test.name, len(weeks), len(self._config.regions)
            )
        return ScanRun(pd.concat(tables, ignore_index=True), scanners)
