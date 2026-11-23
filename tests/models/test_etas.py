from itertools import pairwise

import numpy as np
import pytest

from spacegeo.common.exceptions import NotFittedError
from spacegeo.common.geo import GeoBox, GeoRegion
from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.models.background import KernelBackground
from spacegeo.models.base import ModelData
from spacegeo.models.etas import EtasModel
from spacegeo.models.etas_likelihood import EtasCatalog, EtasLikelihood, EtasPairs
from spacegeo.models.etas_parameters import EtasParameters, EtasSettings
from spacegeo.models.etas_simulation import EtasSimulator
from spacegeo.models.smoothed_poisson import SmoothedPoissonModel

REGION = GeoRegion((GeoBox(0, 8, 100, 108),))
TRUE = EtasParameters(mu=0.25, a=0.25, alpha=1.6, c=0.02, p=1.15, d=40.0, gamma=1.0, q=1.7)
SETTINGS = EtasSettings()
WINDOW = TimeWindow(to_utc("2000-01-01T00:00Z"), to_utc("2014-01-01T00:00Z"))
TRAIN = TimeWindow(WINDOW.start, to_utc("2011-01-01T00:00Z"))
VAL = TimeWindow(TRAIN.end, WINDOW.end)


@pytest.fixture(scope="module")
def catalog():
    return EtasSimulator(REGION, TRUE, np.log(10), SETTINGS).simulate(WINDOW, seed=3)


@pytest.fixture(scope="module")
def fitted(catalog):
    return EtasModel(REGION, SETTINGS).fit(ModelData(catalog, TRAIN))


def test_gradient_matches_finite_differences(catalog) -> None:
    cat = EtasCatalog.from_frame(catalog, REGION, SETTINGS)
    targets = cat.in_span(365.0, 3000.0)
    lik = EtasLikelihood(
        cat,
        EtasPairs.build(cat, targets, SETTINGS),
        np.full(targets.size, 1 / REGION.area_km2),
        (365.0, 3000.0),
        SETTINGS,
    )
    theta = TRUE.to_vector() + 0.1
    _, grad = lik.value_and_grad(theta)
    h = 1e-6
    numeric = [
        (lik.value_and_grad(theta + e)[0] - lik.value_and_grad(theta - e)[0]) / (2 * h)
        for e in np.eye(8) * h
    ]
    np.testing.assert_allclose(grad, numeric, rtol=1e-4, atol=1e-3)


def test_recovers_simulated_parameters(fitted) -> None:
    got = fitted.parameters
    assert got.p == pytest.approx(TRUE.p, abs=0.1)
    assert got.alpha == pytest.approx(TRUE.alpha, abs=0.4)
    assert got.q == pytest.approx(TRUE.q, abs=0.3)
    assert got.branching_ratio(np.log(10)) == pytest.approx(
        TRUE.branching_ratio(np.log(10)), abs=0.15
    )
    assert got.mu == pytest.approx(TRUE.mu, rel=0.25)
    assert ((fitted.background_probabilities > 0) & (fitted.background_probabilities <= 1)).all()


def test_beats_smoothed_poisson_out_of_sample(catalog, fitted) -> None:
    baseline = SmoothedPoissonModel(REGION).fit(ModelData(catalog, TRAIN))
    data = ModelData(catalog, VAL)
    gain = (fitted.log_likelihood(data) - baseline.log_likelihood(data)) / data.n_events
    assert gain > 0.3


def test_window_scores_add_up(catalog, fitted) -> None:
    data = ModelData(catalog, VAL)
    edges = [VAL.start + duration(days=d) for d in (0, 300, 700, 1096)]
    windows = [TimeWindow(a, b) for a, b in pairwise(edges)]
    parts = fitted.log_likelihood_by_window(data, windows)
    whole = fitted.log_likelihood(ModelData(catalog, TimeWindow(edges[0], edges[-1])))
    assert parts.sum() == pytest.approx(whole, rel=1e-9)
    baseline = SmoothedPoissonModel(REGION).fit(ModelData(catalog, TRAIN))
    base_parts = baseline.log_likelihood_by_window(data, windows)
    assert base_parts.sum() == pytest.approx(
        baseline.log_likelihood(ModelData(catalog, TimeWindow(edges[0], edges[-1]))), rel=1e-9
    )


def test_background_integrates_to_one() -> None:
    rng = np.random.default_rng(0)
    lat, lon = REGION.sample(300, rng)
    bg = KernelBackground(REGION, n_mc=4000, seed=1).fit(lat, lon)
    mc_lat, mc_lon = REGION.sample(20000, np.random.default_rng(9))
    integral = bg.density(mc_lat, mc_lon).mean() * REGION.area_km2
    assert integral == pytest.approx(1.0, rel=0.03)
    assert (bg.bandwidths_km >= 10.0).all()


def test_parameters_round_trip_and_validate() -> None:
    assert EtasParameters.from_vector(TRUE.to_vector()) == pytest.approx(TRUE)
    with pytest.raises(ValueError, match="Invalid"):
        EtasParameters(mu=1, a=1, alpha=1, c=1, p=0.9, d=1, gamma=1, q=2)


def test_requires_fit(catalog) -> None:
    with pytest.raises(NotFittedError):
        EtasModel(REGION).log_likelihood(ModelData(catalog, VAL))


def test_rescaled_times_look_like_unit_poisson(catalog, fitted) -> None:
    tau = fitted.rescaled_times(ModelData(catalog, VAL))
    gaps = np.diff(np.concatenate([[0.0], tau]))
    assert (gaps >= 0).all()
    assert gaps.mean() == pytest.approx(1.0, abs=0.1)


def test_forecast_counts_ignore_events_inside_the_window(catalog, fitted) -> None:
    week = TimeWindow(VAL.start, VAL.start + duration(days=7))
    full = fitted.forecast_counts(ModelData(catalog, VAL), [week])
    history_only = catalog.loc[catalog.index < week.start]
    assert fitted.forecast_counts(ModelData(history_only, VAL), [week]) == pytest.approx(full)
    days = (VAL.end - VAL.start) / duration(days=1)
    weeks = [
        TimeWindow(VAL.start + duration(days=d), VAL.start + duration(days=d + 7))
        for d in range(0, int(days) - 7, 7)
    ]
    expected = fitted.forecast_counts(ModelData(catalog, VAL), weeks).sum()
    observed = int(sum(w.mask(catalog.index).sum() for w in weeks))
    assert 0.5 * observed < expected < 1.2 * observed  # no in-window cascades -> some shortfall
