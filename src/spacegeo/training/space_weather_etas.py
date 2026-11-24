"""ETAS + space-weather background modulation (pre-registered experiment).

See ``docs/experiments/space-weather-etas.md``. Per region an ETAS model is
fitted on the training span and then held fixed; a
:class:`~spacegeo.models.modulated_background.ModulatedBackgroundEtas` adds
``c_r * exp(z(t) . beta)`` to its background, with ``z`` the standardised
multi-scale log ratios of one space-weather driver (a *mechanism*).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Literal

import numpy as np
import numpy.typing as npt
import pandas as pd
from pydantic import Field
from scipy import stats

from spacegeo.common.config import BaseConfig
from spacegeo.common.geo import GeoRegion, geomagnetic_latitude_deg
from spacegeo.common.log import get_logger
from spacegeo.common.stats import (
    block_bootstrap_indices,
    holm,
    percentile_interval,
    ratio_of_sums_samples,
)
from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.data.io.omni import OmniReader
from spacegeo.data.io.yearly_archive import YearlyArchive
from spacegeo.models.base import ModelData
from spacegeo.models.etas import EtasComponents, EtasModel
from spacegeo.models.etas_likelihood import EPOCH
from spacegeo.models.modulated_background import HourlyCovariates, ModulatedBackgroundEtas
from spacegeo.training.etas_baseline import ValidationExperimentConfig
from spacegeo.training.space_weather_covariates import SpaceWeatherCovariates

_log = get_logger(__name__)
_ALPHA = 0.05

Array = npt.NDArray[np.float64]


class MechanismConfig(BaseConfig):
    """One pre-registered mechanism: a name and the registered feature that measures it."""

    name: str
    feature: str


class ShiftTestConfig(BaseConfig):
    """Circular-shift null: number of shifts and smallest allowed offset."""

    shifts: int = Field(default=199, ge=19)
    min_offset_days: float = Field(default=365.0, gt=0)


class ExploratoryConfig(BaseConfig):
    """Exploratory variants (reported, never used for a detection claim)."""

    joint_model: bool = True
    extra_tau_days: float | None = None


class SpaceWeatherSettings(BaseConfig):
    """Space-weather inputs and feature settings.

    Attributes:
        archive: Committed OMNI2 archive directory.
        mechanisms: Primary tests, one per mechanism.
        taus_days: Short smoothing scales, days.
        detrend_days: Long detrending scale and feature lookback, days.
        min_weight_fraction: Minimum observed share of each average's weight.
        shift_test: Circular-shift null settings.
        exploratory: Exploratory variants.
    """

    archive: Path
    mechanisms: tuple[MechanismConfig, ...] = Field(min_length=1)
    taus_days: tuple[float, ...] = Field(min_length=1)
    detrend_days: float = 365.0
    min_weight_fraction: float = Field(default=0.5, gt=0, le=1)
    shift_test: ShiftTestConfig = ShiftTestConfig()
    exploratory: ExploratoryConfig = ExploratoryConfig()


class SpaceWeatherEtasConfig(ValidationExperimentConfig):
    """Config of ``experiment: space_weather_etas``."""

    experiment: Literal["space_weather_etas"]
    space_weather: SpaceWeatherSettings

    @property
    def fit_window(self) -> TimeWindow:
        """Training span after the ETAS burn-in (scored and fitted)."""
        start = to_utc(self.train_start) + duration(days=self.etas.burn_in_days)
        return TimeWindow(start, to_utc(self.val_start))


@dataclass(frozen=True)
class Variant:
    """One model to fit: which features, which scales, and whether it is primary."""

    name: str
    primary: bool
    features: tuple[str, ...]
    taus_days: tuple[float, ...]


@dataclass(frozen=True)
class VariantResult:
    """Scores of one variant.

    Attributes:
        summary: Scalars (gain, interval, shift p-value, beta and intervals, ...).
        gains: Validation log-likelihood gain over ETAS, weeks x regions, nats.
        shift_gains: Pooled gain of each circular shift (primary variants only).
    """

    summary: dict[str, Any]
    gains: Array
    shift_gains: Array


@dataclass(frozen=True)
class SpaceWeatherEtasResult:
    """Everything the report needs.

    Attributes:
        variants: One row per variant (primary first), with Holm-adjusted p.
        per_region: Per-region gain per event for each variant, plus counts
            and geomagnetic latitude.
        weekly: Long frame ``week, region, variant, n, gain``.
        shift_null: Variant name -> pooled gains under circular shifts.
        missing: Covariate name -> share of grid hours set to 0 (missing).
        beta_resamples: Refits behind each beta interval.
    """

    variants: pd.DataFrame
    per_region: pd.DataFrame
    weekly: pd.DataFrame
    shift_null: dict[str, Array]
    missing: dict[str, float]
    beta_resamples: int


@dataclass(frozen=True)
class _Components:
    """Fixed ETAS components for the fit span and the validation span, by region."""

    train: dict[str, EtasComponents]
    validation: dict[str, EtasComponents]


class SpaceWeatherEtasExperiment:
    """Runs the pre-registered comparison on the validation span.

    Args:
        config: Experiment config.
        regions: Region name -> geometry.
        catalog: Earthquake catalog; events at or after ``val_end`` are dropped.
        space_weather: OMNI2 hourly frame; rows at or after ``val_end`` are dropped.
    """

    BETA_RESAMPLES: ClassVar[int] = 500
    """Block-bootstrap refits for the beta intervals (not fixed by the pre-registration)."""

    def __init__(
        self,
        config: SpaceWeatherEtasConfig,
        regions: dict[str, GeoRegion],
        catalog: pd.DataFrame,
        space_weather: pd.DataFrame,
    ) -> None:
        end = to_utc(config.val_end)
        self._config = config
        self._regions = regions
        self._catalog = catalog.loc[catalog.index < end]
        self._covariates = SpaceWeatherCovariates(
            space_weather.loc[space_weather.index < end],
            TimeWindow(config.fit_window.start, end),
            to_utc(config.val_start),
        )
        self._weeks = [self._days(w) for w in config.validation_weeks()]
        self._rng = np.random.default_rng(config.seed)

    @staticmethod
    def load_inputs(root: Path, config: SpaceWeatherEtasConfig) -> dict[str, Any]:
        """Read the OMNI2 archive for the training and validation spans only."""
        window = TimeWindow(to_utc(config.train_start), to_utc(config.val_end))
        archive = YearlyArchive(root / config.space_weather.archive, OmniReader.schema)
        return {"space_weather": archive.read(window)}

    def run(self) -> SpaceWeatherEtasResult:
        """Fit ETAS per region, then every variant; summarise."""
        comps = self._etas_components()
        counts = self._weekly_counts(comps.validation)
        results = {v.name: self._variant(v, comps, counts) for v in self._variants()}
        return self._assemble(results, counts)

    def _variants(self) -> list[Variant]:
        sw = self._config.space_weather
        taus = tuple(sw.taus_days)
        out = [Variant(m.name, True, (m.feature,), taus) for m in sw.mechanisms]
        if sw.exploratory.joint_model:
            out.append(Variant("joint", False, tuple(m.feature for m in sw.mechanisms), taus))
        extra = sw.exploratory.extra_tau_days
        if extra is not None:
            out += [
                Variant(f"{m.name}+{extra:g}d", False, (m.feature,), (*taus, extra))
                for m in sw.mechanisms
            ]
        return out

    def _etas_components(self) -> _Components:
        settings = self._config.etas.settings(self._config.mc)
        train, val = {}, {}
        for name, region in self._regions.items():
            _log.info("Fitting ETAS for %s", name)
            model = EtasModel(region, settings).fit(ModelData(self._catalog, self._config.train))
            train[name] = model.components(ModelData(self._catalog, self._config.fit_window))
            val[name] = model.components(ModelData(self._catalog, self._config.validation))
        return _Components(train, val)

    def _variant(self, variant: Variant, comps: _Components, counts: Array) -> VariantResult:
        _log.info("Variant %s", variant.name)
        sw = self._config.space_weather
        features = self._covariates.features(
            variant.features, variant.taus_days, sw.detrend_days, sw.min_weight_fraction
        )
        raw = self._covariates.raw(features)
        z = self._covariates.standardised(raw)
        model = ModulatedBackgroundEtas(z).fit(comps.train, self._fit_span())
        gains = model.gain_by_window(comps.validation, self._weeks)
        shift = self._shift_null(raw, comps, counts) if variant.primary else np.empty(0)
        summary = {
            "variant": variant.name,
            "primary": variant.primary,
            **self._gain_summary(gains, counts),
            **self._beta_summary(z, model.beta, comps),
            **self._shift_summary(float(gains.sum() / counts.sum()), shift),
            "missing_hours": float(np.mean(list(self._covariates.missing_fraction(raw).values()))),
        }
        return VariantResult(summary=summary, gains=gains, shift_gains=shift)

    def _gain_summary(self, gains: Array, counts: Array) -> dict[str, float]:
        idx = self._config.bootstrap_indices(len(gains))
        low, high = percentile_interval(ratio_of_sums_samples(gains, counts, idx))
        return {
            "info_gain_per_event": float(gains.sum() / counts.sum()),
            "info_gain_lo": low,
            "info_gain_hi": high,
        }

    def _beta_summary(
        self, z: HourlyCovariates, beta: Array, comps: _Components
    ) -> dict[str, float]:
        samples = self._beta_bootstrap(z, comps)
        low, high = percentile_interval(samples.sum(axis=1))
        out: dict[str, float] = {
            "sustained_change_pct": 100 * float(np.expm1(beta.sum())),
            "sustained_change_lo": 100 * float(np.expm1(low)),
            "sustained_change_hi": 100 * float(np.expm1(high)),
        }
        for k, name in enumerate(z.names):
            low, high = percentile_interval(samples[:, k])
            out[f"rate_change_pct[{name}]"] = 100 * float(np.expm1(beta[k]))
            out[f"rate_change_lo[{name}]"] = 100 * float(np.expm1(low))
            out[f"rate_change_hi[{name}]"] = 100 * float(np.expm1(high))
        return out

    def _beta_bootstrap(self, z: HourlyCovariates, comps: _Components) -> Array:
        """Refit on moving-block resamples of 7-day blocks of the fit span."""
        start, end = self._fit_span()
        n_weeks = int(np.ceil((end - start) / 7))
        idx = block_bootstrap_indices(
            n_weeks, self._config.bootstrap_block_weeks, self.BETA_RESAMPLES, self._config.seed
        )
        hour_week = ((np.arange(len(z.span_rows(start, end))) + 0.5) / 24 // 7).astype(np.int64)
        event_week = {n: ((c.times - start) // 7).astype(np.int64) for n, c in comps.train.items()}
        samples = np.empty((self.BETA_RESAMPLES, len(z.names)))
        for b in range(self.BETA_RESAMPLES):
            mult = np.bincount(idx[b], minlength=n_weeks).astype(np.float64)
            weights = {n: mult[w] for n, w in event_week.items()}
            model = ModulatedBackgroundEtas(z).fit(
                comps.train, (start, end), weights, mult[hour_week]
            )
            samples[b] = model.beta
        return samples

    def _shift_null(self, raw: pd.DataFrame, comps: _Components, counts: Array) -> Array:
        test = self._config.space_weather.shift_test
        low = round(test.min_offset_days * 24)
        offsets = self._rng.integers(low, self._covariates.n_rows - low + 1, size=test.shifts)
        out = np.empty(test.shifts)
        for i, offset in enumerate(offsets):
            z = self._covariates.standardised(raw, int(offset))
            model = ModulatedBackgroundEtas(z).fit(comps.train, self._fit_span())
            out[i] = model.gain_by_window(comps.validation, self._weeks).sum() / counts.sum()
        return out

    @staticmethod
    def _shift_summary(gain: float, shift: Array) -> dict[str, float]:
        if shift.size == 0:
            return {"p_shift": np.nan, "shift_gain_p95": np.nan}
        return {
            "p_shift": float((1 + (shift >= gain).sum()) / (1 + shift.size)),
            "shift_gain_p95": float(np.percentile(shift, 95)),
        }

    def _assemble(self, results: dict[str, VariantResult], counts: Array) -> SpaceWeatherEtasResult:
        table = pd.DataFrame([r.summary for r in results.values()]).set_index("variant")
        primary = table["primary"].to_numpy(dtype=bool)
        p_holm = np.full(len(table), np.nan)
        p_holm[primary] = holm(table.loc[primary, "p_shift"].to_numpy(dtype=np.float64))
        table["p_shift_holm"] = p_holm
        table["detected"] = primary & (p_holm < _ALPHA) & (table["info_gain_lo"].to_numpy() > 0)
        per_region = self._per_region(results, counts)
        table = self._latitude_tests(table, per_region)
        return SpaceWeatherEtasResult(
            variants=table,
            per_region=per_region,
            weekly=self._weekly(results, counts),
            shift_null={k: r.shift_gains for k, r in results.items() if r.shift_gains.size},
            missing=self._missing(),
            beta_resamples=self.BETA_RESAMPLES,
        )

    def _per_region(self, results: dict[str, VariantResult], counts: Array) -> pd.DataFrame:
        names = list(self._regions)
        centroids = [self._regions[n].centroid for n in names]
        lat = [c.lat_deg for c in centroids]
        lon = [c.lon_deg for c in centroids]
        frame = pd.DataFrame(
            {
                "n_val": counts.sum(axis=0),
                "geomagnetic_lat_deg": geomagnetic_latitude_deg(lat, lon),
            },
            index=pd.Index(names, name="region"),
        )
        for key, r in results.items():
            frame[f"gain[{key}]"] = r.gains.sum(axis=0) / np.maximum(counts.sum(axis=0), 1.0)
        return frame

    @staticmethod
    def _latitude_tests(table: pd.DataFrame, per_region: pd.DataFrame) -> pd.DataFrame:
        maglat = np.abs(per_region["geomagnetic_lat_deg"].to_numpy(dtype=np.float64))
        rho, p = [], []
        for key in table.index:
            test = stats.spearmanr(
                maglat, per_region[f"gain[{key}]"].to_numpy(), alternative="greater"
            )
            rho.append(float(np.asarray(test[0])))
            p.append(float(np.asarray(test[1])))
        return table.assign(maglat_spearman_rho=rho, maglat_spearman_p=p)

    def _weekly(self, results: dict[str, VariantResult], counts: Array) -> pd.DataFrame:
        weeks = [w.start for w in self._config.validation_weeks()]
        frames = []
        for key, r in results.items():
            for j, region in enumerate(self._regions):
                frames.append(
                    pd.DataFrame(
                        {
                            "week": weeks,
                            "region": region,
                            "variant": key,
                            "n": counts[:, j],
                            "gain": r.gains[:, j],
                        }
                    )
                )
        return pd.concat(frames, ignore_index=True)

    def _missing(self) -> dict[str, float]:
        sw = self._config.space_weather
        features = self._covariates.features(
            [m.feature for m in sw.mechanisms],
            sw.taus_days,
            sw.detrend_days,
            sw.min_weight_fraction,
        )
        return self._covariates.missing_fraction(self._covariates.raw(features))

    def _weekly_counts(self, validation: dict[str, EtasComponents]) -> Array:
        return np.array(
            [
                [((c.times >= t0) & (c.times < t1)).sum() for c in validation.values()]
                for t0, t1 in self._weeks
            ],
            dtype=np.float64,
        )

    def _fit_span(self) -> tuple[float, float]:
        return self._days(self._config.fit_window)

    @staticmethod
    def _days(window: TimeWindow) -> tuple[float, float]:
        day = duration(days=1)
        return float((window.start - EPOCH) / day), float((window.end - EPOCH) / day)
