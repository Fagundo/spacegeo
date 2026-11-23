"""Weekly anomaly scan over the validation span and the live test span."""

from __future__ import annotations

from collections.abc import Callable
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
        self._tests = tests or self._default_tests(config, catalog)

    @staticmethod
    def _default_tests(config: WeeklyScanConfig, catalog: pd.DataFrame) -> tuple[ScanTest, ...]:
        horizon = duration(days=config.horizon_days)
        cut = MagnitudeCut(config.mc).transform(catalog)
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

    def validate(self) -> pd.DataFrame:
        """Fit on the training span and score every validation week."""
        return self._run(self._config.train, self.weeks(self._config.validation))

    def predict(self, as_of: pd.Timestamp) -> pd.DataFrame:
        """Fit on train + validation and score every complete test week before ``as_of``."""
        stop = to_utc(as_of)
        start = to_utc(self._config.test_start)
        if stop <= start:
            raise ValueError(f"as_of {stop} is not after test_start {start}.")
        return self._run(self._config.refit, self.weeks(TimeWindow(start, stop)))

    def _run(self, fit_window: TimeWindow, weeks: list[TimeWindow]) -> pd.DataFrame:
        if not weeks:
            raise ValueError("No complete weeks to score.")
        tables = []
        for test in self._tests:
            scanner = RegionalAnomalyScanner(
                self._config.regions, test.model_factory, self._config.fdr
            )
            table = scanner.fit(test.events, fit_window).score(test.events, weeks)
            table.insert(0, "test", test.name)
            tables.append(table)
            _log.info(
                "%s: scored %d weeks x %d regions", test.name, len(weeks), len(self._config.regions)
            )
        return pd.concat(tables, ignore_index=True)
