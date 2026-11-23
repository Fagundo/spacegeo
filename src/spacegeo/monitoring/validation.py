"""Everything computed on the validation span, assembled in one place."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import pandas as pd

from spacegeo.common.time import duration
from spacegeo.evaluation.anomaly import RegionalAnomalyScanner
from spacegeo.models.base import CountModel
from spacegeo.models.count import EmpiricalCountModel, NegativeBinomialCountModel, PoissonCountModel
from spacegeo.monitoring.calibration import CalibrationSummary
from spacegeo.monitoring.config import WeeklyScanConfig
from spacegeo.monitoring.injection import InjectionStudy
from spacegeo.monitoring.model_comparison import ModelComparison
from spacegeo.monitoring.weekly_scan import WeeklyAnomalyScan


@dataclass(frozen=True)
class ValidationReport:
    """Validation outputs.

    Attributes:
        results: Scored validation region-weeks for the live tests.
        by_test: Calibration verdict and summary per test.
        by_region: Observed vs. expected and flags per test and region.
        pit_histogram: PIT bin shares per test.
        model_comparison: Log score / information gain per catalog and model.
        power: Detection rate per test, region and injected burst size.
        min_detectable: Smallest burst reaching 80% power per test and region.
    """

    results: pd.DataFrame
    by_test: pd.DataFrame
    by_region: pd.DataFrame
    pit_histogram: pd.DataFrame
    model_comparison: pd.DataFrame
    power: pd.DataFrame
    min_detectable: pd.DataFrame


class ValidationSuite:
    """Calibration, model comparison and injection power on validation weeks.

    Args:
        config: Scan configuration.
        scan: The weekly scan (holds the catalogs and live tests).
        candidates: Models compared by log score (default: Poisson, negative
            binomial, empirical).
        sizes: Burst sizes for the injection study.
    """

    def __init__(
        self,
        config: WeeklyScanConfig,
        scan: WeeklyAnomalyScan,
        candidates: Mapping[str, Callable[[], CountModel]] | None = None,
        sizes: Sequence[int] = (2, 5, 10, 20, 40, 80, 160),
    ) -> None:
        horizon = duration(days=config.horizon_days)
        self._config = config
        self._scan = scan
        self._candidates = candidates or {
            "poisson": lambda: PoissonCountModel(horizon),
            "negative_binomial": lambda: NegativeBinomialCountModel(horizon),
            "empirical": lambda: EmpiricalCountModel(horizon),
        }
        self._sizes = tuple(sizes)
        self._calibration = CalibrationSummary(alpha=config.fdr)

    def run(self) -> ValidationReport:
        """Compute every validation output."""
        run = self._scan.validate()
        results = run.results
        comparison = ModelComparison(self._config.regions, self._candidates, alpha=self._config.fdr)
        catalogs = {t.name: t.events for t in self._scan.tests}
        power = self._power(results, run.scanners)
        return ValidationReport(
            results=results,
            by_test=self._calibration.by_test(results),
            by_region=self._calibration.by_region(results),
            pit_histogram=self._calibration.pit_histogram(results),
            model_comparison=comparison.compare(
                catalogs, self._config.train, self._scan.validation_weeks()
            ),
            power=power,
            min_detectable=self._min_detectable(power),
        )

    def _power(
        self, results: pd.DataFrame, scanners: Mapping[str, RegionalAnomalyScanner]
    ) -> pd.DataFrame:
        tables = []
        for name, table in results.groupby("test", sort=True):
            models = scanners[str(name)].models
            power = InjectionStudy(models, self._config.fdr, self._sizes).power(table).reset_index()
            power.insert(0, "test", name)
            tables.append(power)
        return pd.concat(tables, ignore_index=True)

    @staticmethod
    def _min_detectable(power: pd.DataFrame) -> pd.DataFrame:
        frames = []
        for name, table in power.groupby("test", sort=True):
            series = InjectionStudy.minimum_detectable(table.set_index(["region", "added"]))
            frames.append(series.reset_index().assign(test=name))
        return pd.concat(frames, ignore_index=True).loc[
            :, ["test", "region", "min_detectable_added"]
        ]
