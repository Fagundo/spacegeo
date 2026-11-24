import numpy as np
import pytest
from scipy.optimize import check_grad

from spacegeo.models.etas import EtasComponents
from spacegeo.models.modulated_background import (
    HourlyCovariates,
    ModulatedBackgroundEtas,
    _Stacked,
)

HOURS = 24 * 400


def _covariates(seed: int = 0) -> HourlyCovariates:
    rng = np.random.default_rng(seed)
    z = np.convolve(rng.normal(size=HOURS + 47), np.ones(48) / np.sqrt(48), mode="valid")
    return HourlyCovariates(0.0, np.asarray(z[:HOURS, None], dtype=np.float64), ("z",))


def _simulate(cov: HourlyCovariates, beta: float, mu: float, seed: int) -> EtasComponents:
    """Background-only events (u = 1 km^-2 at every event, no triggering)."""
    rng = np.random.default_rng(seed)
    rate = mu * np.exp(beta * cov.values[:, 0]) * cov.step_days
    counts = rng.poisson(rate)
    hours = np.repeat(np.arange(HOURS), counts)
    times = (hours + rng.uniform(size=hours.size)) * cov.step_days
    times.sort()
    return EtasComponents(
        times=times,
        background=np.full(times.size, mu),
        triggered=np.full(times.size, 1e-12),
        mu=mu,
    )


def test_recovers_shared_beta_and_region_normalisers() -> None:
    cov = _covariates()
    regions = {"a": _simulate(cov, 0.4, 5.0, 1), "b": _simulate(cov, 0.4, 2.0, 2)}
    model = ModulatedBackgroundEtas(cov).fit(regions, (0.0, HOURS / 24))
    assert model.beta[0] == pytest.approx(0.4, abs=0.05)
    assert model.log_c["a"] == pytest.approx(0.0, abs=0.06)  # simulated with c = 1


def test_gradient_matches_finite_differences() -> None:
    cov = _covariates()
    regions = [_simulate(cov, 0.3, 4.0, 3), _simulate(cov, 0.0, 1.0, 4)]
    regions = [
        EtasComponents(r.times, r.background, np.full(r.times.size, 0.7), r.mu) for r in regions
    ]
    events = _Stacked.build(regions, cov, None)
    hours = cov.values
    weights = np.random.default_rng(5).integers(0, 3, size=HOURS).astype(float)
    model = ModulatedBackgroundEtas(cov)
    theta = np.array([0.2, 0.1, -0.3])

    def f(t: np.ndarray) -> float:
        return model._objective(t, events, hours, weights)[0]

    def g(t: np.ndarray) -> np.ndarray:
        return model._objective(t, events, hours, weights)[1]

    assert check_grad(f, g, theta) < 1e-3 * max(1.0, abs(f(theta)))


def test_no_signal_gives_no_out_of_sample_gain() -> None:
    cov = _covariates(7)
    half = HOURS // 2 / 24
    comp = _simulate(cov, 0.0, 8.0, 8)
    train = {"a": _restrict(comp, 0.0, half)}
    model = ModulatedBackgroundEtas(cov).fit(train, (0.0, half))
    gain = model.gain_by_window({"a": _restrict(comp, half, HOURS / 24)}, [(half, HOURS / 24)])
    assert gain[0, 0] / comp.times.size < 0.01


def _restrict(c: EtasComponents, t0: float, t1: float) -> EtasComponents:
    m = (c.times >= t0) & (c.times < t1)
    return EtasComponents(c.times[m], c.background[m], c.triggered[m], c.mu)
