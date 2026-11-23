"""Weekly "M >= X in this region" forecasts: tabular models vs. ETAS.

Builds one row per region-week with features computed strictly before the
week starts (including ETAS's own forecast for that week), fits tabular
models on training weeks and scores them on validation weeks with the
Bernoulli log score.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import numpy as np
import numpy.typing as npt
import pandas as pd
from pydantic import AwareDatetime, Field
from sklearn.metrics import roc_auc_score

from spacegeo.common.config import BaseConfig
from spacegeo.common.geo import GeoRegion
from spacegeo.common.log import get_logger
from spacegeo.common.stats import percentile_interval
from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.features.base import FeatureSet
from spacegeo.features.seismicity import (
    BValue,
    DaysSinceMagnitude,
    EventCount,
    MaxMagnitude,
    MeanDepth,
)
from spacegeo.models.base import ModelData, TabularEventModel
from spacegeo.models.etas import EtasModel
from spacegeo.models.tabular import (
    BoostingParams,
    ClimatologyEventModel,
    GradientBoostingEventModel,
    LogisticEventModel,
)
from spacegeo.training.etas_baseline import ValidationExperimentConfig

_log = get_logger(__name__)
_WEEK = duration(days=7)
REFERENCE = "etas_recalibrated"
"""The pre-registered reference model."""


class BoostingConfig(BaseConfig):
    """Fixed gradient-boosting hyperparameters (see :class:`BoostingParams`)."""

    max_iter: int = Field(default=200, ge=1)
    learning_rate: float = Field(default=0.05, gt=0)
    max_depth: int = Field(default=3, ge=1)
    min_samples_leaf: int = Field(default=50, ge=1)
    l2_regularization: float = Field(default=1.0, ge=0)
    seed: int = 0

    @property
    def params(self) -> BoostingParams:
        """As :class:`BoostingParams`."""
        return BoostingParams(**self.model_dump())


class EventForecastConfig(ValidationExperimentConfig):
    """Config of a weekly event-forecast run (``experiment: event_forecast``).

    Attributes:
        target_magnitude: Primary target: at least one event this large in the week.
        secondary_target_magnitude: Secondary target, reported only.
        history_start: First event used (history for features and ETAS burn-in).
        boosting: Gradient-boosting hyperparameters.
    """

    experiment: Literal["event_forecast"]
    target_magnitude: float = 6.0
    secondary_target_magnitude: float = 7.0
    history_start: AwareDatetime
    boosting: BoostingConfig = BoostingConfig()

    def weeks(self, start: AwareDatetime, end: AwareDatetime) -> list[TimeWindow]:
        """Whole anchored weeks in ``[start, end)``."""
        return self.weeks_between(start, end)


@dataclass(frozen=True)
class EventForecastResult:
    """Run outputs.

    Attributes:
        predictions: Validation region-weeks with outcomes and each model's probability.
        scores: One row per (target, model): log score, gains with intervals, Brier, AUC.
        reliability: Binned predicted vs. observed frequency for the primary target.
        importance: Permutation importance of the boosting features (validation).
    """

    predictions: pd.DataFrame
    scores: pd.DataFrame
    reliability: pd.DataFrame
    importance: pd.DataFrame


def _feature_set(mc: float) -> FeatureSet:
    def days(n: int) -> pd.Timedelta:
        return duration(days=n)

    return FeatureSet(
        [
            EventCount(days(7), mc),
            EventCount(days(30), mc),
            EventCount(days(365), mc),
            EventCount(days(30), 5.5),
            EventCount(days(365), 5.5),
            MaxMagnitude(days(7)),
            MaxMagnitude(days(30)),
            MaxMagnitude(days(365)),
            DaysSinceMagnitude(days(7305), 6.0),
            DaysSinceMagnitude(days(7305), 7.0),
            BValue(days(1826), mc, 200),
            MeanDepth(days(30)),
        ]
    )


class RegionWeekTable:
    """Feature rows and outcomes for every week of one region.

    Args:
        config: Experiment config.
        features: Seismicity features.
    """

    def __init__(self, config: EventForecastConfig, features: FeatureSet) -> None:
        self._config = config
        self._features = features

    def build(
        self, name: str, region: GeoRegion, catalog: pd.DataFrame, weeks: list[TimeWindow]
    ) -> pd.DataFrame:
        """One row per week: identifiers, features, ETAS forecasts and outcomes."""
        local = self._local(region, catalog)
        starts = pd.DatetimeIndex([w.start for w in weeks])
        table = self._features.compute(local, starts).reset_index(drop=True)
        table.insert(0, "region", name)
        table.insert(0, "week", starts)
        etas = self._etas(region, catalog)
        counts = etas.forecast_counts(ModelData(catalog, self._span(weeks)), weeks)
        table["log_etas_count_m0"] = np.log(np.maximum(counts, 1e-12))
        for key, magnitude in self._targets().items():
            drop = magnitude - self._config.mc
            table[f"log_etas_count_{key}"] = table["log_etas_count_m0"] - etas.beta * drop
            table[key] = self._outcomes(local, weeks, magnitude)
        return table

    def _targets(self) -> dict[str, float]:
        return {
            "y_primary": self._config.target_magnitude,
            "y_secondary": self._config.secondary_target_magnitude,
        }

    def _local(self, region: GeoRegion, catalog: pd.DataFrame) -> pd.DataFrame:
        inside = region.contains(catalog["lat_deg"], catalog["lon_deg"])
        keep = inside & (catalog["mag"].to_numpy() >= self._config.mc - 1e-9)
        return catalog.loc[keep].sort_index()

    def _etas(self, region: GeoRegion, catalog: pd.DataFrame) -> EtasModel:
        fit_window = TimeWindow(to_utc(self._config.history_start), to_utc(self._config.val_start))
        model = EtasModel(region, self._config.etas.settings(self._config.mc))
        return model.fit(ModelData(catalog, fit_window))

    @staticmethod
    def _span(weeks: list[TimeWindow]) -> TimeWindow:
        return TimeWindow(weeks[0].start, weeks[-1].end)

    @staticmethod
    def _outcomes(local: pd.DataFrame, weeks: list[TimeWindow], magnitude: float) -> npt.NDArray:
        big = local.index[local["mag"].to_numpy() >= magnitude - 1e-9]
        return np.array([int(w.mask(big).any()) for w in weeks], dtype=np.int64)


class EventForecastExperiment:
    """Fits the models on training region-weeks and scores validation region-weeks.

    Args:
        config: Experiment config.
        regions: Region name -> geometry.
        catalog: Catalog; events at or after ``val_end`` are dropped here.
    """

    def __init__(
        self, config: EventForecastConfig, regions: dict[str, GeoRegion], catalog: pd.DataFrame
    ) -> None:
        self._config = config
        self._regions = regions
        self._catalog = catalog.loc[
            (catalog.index >= to_utc(config.history_start))
            & (catalog.index < to_utc(config.val_end))
        ]

    def run(self) -> EventForecastResult:
        """Build the table, fit, score."""
        table = self._table()
        train = table.loc[table["week"] < to_utc(self._config.val_start)].reset_index(drop=True)
        val = table.loc[table["week"] >= to_utc(self._config.val_start)].reset_index(drop=True)
        predictions, scores, boosting = [], [], None
        for target in ("y_primary", "y_secondary"):
            probs, fitted = self._predict(train, val, target)
            if target == "y_primary":
                boosting = fitted
            scores.append(self._score(val, probs, target))
            predictions.append(pd.DataFrame({f"{target}__{k}": v for k, v in probs.items()}))
        if boosting is None:
            raise RuntimeError("Primary target was not fitted.")
        pred = pd.concat(
            [val[["week", "region", "y_primary", "y_secondary"]], *predictions], axis=1
        )
        return EventForecastResult(
            predictions=pred,
            scores=pd.concat(scores, ignore_index=True),
            reliability=self._reliability(pred),
            importance=self._importance(boosting, val),
        )

    def _table(self) -> pd.DataFrame:
        weeks = self._config.weeks(self._config.train_start, self._config.val_end)
        builder = RegionWeekTable(self._config, _feature_set(self._config.mc))
        frames = []
        for name, region in self._regions.items():
            _log.info("Building region-weeks for %s", name)
            frames.append(builder.build(name, region, self._catalog, weeks))
        return pd.concat(frames, ignore_index=True)

    def _models(self, target: str) -> dict[str, Callable[[], TabularEventModel]]:
        params = self._config.boosting.params
        # The secondary-target ETAS column is a fixed shift of the primary one per
        # region, so it is left out to keep the pre-registered feature list.
        exclude = ("week", "y_primary", "y_secondary", "log_etas_count_y_secondary")
        return {
            "climatology": lambda: ClimatologyEventModel("region"),
            REFERENCE: lambda: LogisticEventModel([f"log_etas_count_{target}"]),
            "gradient_boosting": lambda: GradientBoostingEventModel(
                exclude=exclude, categorical=("region",), params=params
            ),
        }

    def _predict(
        self, train: pd.DataFrame, val: pd.DataFrame, target: str
    ) -> tuple[dict[str, npt.NDArray[np.float64]], TabularEventModel]:
        expected = np.exp(val[f"log_etas_count_{target}"].to_numpy())
        probs = {"etas_raw": np.clip(1 - np.exp(-expected), 1e-6, 1 - 1e-6)}
        fitted: TabularEventModel | None = None
        for name, factory in self._models(target).items():
            model = factory().fit(train, pd.Series(train[target], index=train.index))
            probs[name] = model.predict_proba(val)
            fitted = model if name == "gradient_boosting" else fitted
        if fitted is None:
            raise RuntimeError("No boosting model fitted.")
        return probs, fitted

    def _score(
        self, val: pd.DataFrame, probs: dict[str, npt.NDArray[np.float64]], target: str
    ) -> pd.DataFrame:
        y = val[target].to_numpy()
        weeks = pd.factorize(val["week"])[0]
        logs = {k: y * np.log(p) + (1 - y) * np.log(1 - p) for k, p in probs.items()}
        idx = self._config.bootstrap_indices(int(weeks.max()) + 1)
        brier_clim = float(((probs["climatology"] - y) ** 2).mean())
        rows = []
        for name, p in probs.items():
            row: dict[str, float | str] = {
                "target": target,
                "model": name,
                "mean_log_score": float(logs[name].mean()),
                "brier_skill_vs_climatology": 1 - float(((p - y) ** 2).mean()) / brier_clim,
                "roc_auc": float(roc_auc_score(y, p)) if 0 < y.sum() < y.size else np.nan,
                "base_rate": float(y.mean()),
            }
            for ref in (REFERENCE, "climatology"):
                row.update(self._gain(logs[name] - logs[ref], weeks, idx, ref))
            rows.append(row)
        return pd.DataFrame(rows)

    @staticmethod
    def _gain(
        diff: npt.NDArray[np.float64],
        weeks: npt.NDArray[np.int64],
        idx: npt.NDArray[np.int64],
        ref: str,
    ) -> dict[str, float]:
        n_weeks = int(weeks.max()) + 1
        per_week = np.bincount(weeks, weights=diff, minlength=n_weeks)
        rows = np.bincount(weeks, minlength=n_weeks).astype(np.float64)
        samples = per_week[idx].sum(axis=1) / rows[idx].sum(axis=1)
        low, high = percentile_interval(samples)
        return {
            f"gain_vs_{ref}": float(diff.mean()),
            f"gain_vs_{ref}_lo": low,
            f"gain_vs_{ref}_hi": high,
        }

    @staticmethod
    def _reliability(pred: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
        rows = []
        for model in ("gradient_boosting", REFERENCE, "etas_raw"):
            p = pred[f"y_primary__{model}"].to_numpy()
            edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
            which = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, edges.size - 2)
            for b in range(edges.size - 1):
                inside = which == b
                if inside.any():
                    rows.append(
                        {
                            "model": model,
                            "bin": b,
                            "mean_predicted": float(p[inside].mean()),
                            "observed_frequency": float(
                                pred["y_primary"].to_numpy()[inside].mean()
                            ),
                            "n": int(inside.sum()),
                        }
                    )
        return pd.DataFrame(rows)

    def _importance(self, model: TabularEventModel, val: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(model, GradientBoostingEventModel):
            return pd.DataFrame()
        rng = np.random.default_rng(self._config.seed)
        y = val["y_primary"].to_numpy()

        def log_loss(frame: pd.DataFrame) -> float:
            p = model.predict_proba(frame)
            return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())

        base = log_loss(val)
        rows = []
        for col in model.feature_names:
            shuffled = val.copy()
            shuffled[col] = rng.permutation(shuffled[col].to_numpy())
            rows.append({"feature": col, "log_loss_increase": log_loss(shuffled) - base})
        return pd.DataFrame(rows).sort_values("log_loss_increase", ascending=False)
