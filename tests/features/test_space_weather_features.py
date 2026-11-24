import numpy as np
import pandas as pd
import pytest

from spacegeo.common.time import to_utc
from spacegeo.features.bz_sigma import BzSigma
from spacegeo.features.dynamic_pressure import DynamicPressure
from spacegeo.features.newell_coupling import NewellCoupling


def _hourly(days: int, columns: dict[str, np.ndarray]) -> pd.DataFrame:
    index = pd.date_range("2020-01-01", periods=24 * days, freq="h", tz="UTC")
    return pd.DataFrame({k: v[: len(index)] for k, v in columns.items()}, index=index)


def _positive(n: int, seed: int = 1) -> np.ndarray:
    return np.exp(np.random.default_rng(seed).normal(size=n))


def test_fast_path_matches_reference_with_gaps() -> None:
    values = _positive(24 * 20)
    values[100:140] = np.nan
    data = _hourly(20, {"sigma_bz_nT": values})
    feature = BzSigma(taus_days=(0.25, 1.0), detrend_days=6.0)
    times = pd.DatetimeIndex(data.index[150::37])
    fast = feature.compute(data, times)
    slow = pd.DataFrame(
        [
            feature._row(data.loc[(data.index >= t - feature.lookback) & (data.index < t)], t)
            for t in times
        ],
        index=times,
        columns=list(feature.output_names),
    )
    pd.testing.assert_frame_equal(fast, slow, rtol=1e-9, atol=1e-12)


def test_constant_driver_gives_zero_log_ratio() -> None:
    data = _hourly(12, {"pdyn_nPa": np.full(24 * 12, 2.0)})
    feature = DynamicPressure(taus_days=(0.5,), detrend_days=4.0)
    out = feature.compute(data, pd.DatetimeIndex([to_utc("2020-01-10T00:00Z")]))
    assert out.iloc[0, 0] == pytest.approx(0.0, abs=1e-12)
    assert list(out.columns) == ["pdyn_nPa_logratio_0.5d_vs_4d"]


def test_recent_jump_raises_short_scale_most() -> None:
    values = np.full(24 * 12, 1.0)
    values[-24:] = 10.0
    data = _hourly(12, {"pdyn_nPa": values})
    feature = DynamicPressure(taus_days=(0.5, 2.0), detrend_days=8.0)
    out = feature.compute(data, pd.DatetimeIndex([data.index[-1] + pd.Timedelta(hours=1)]))
    short, long = out.iloc[0].to_numpy()
    assert short > long > 0


def test_mostly_missing_window_is_nan_not_filled() -> None:
    values = _positive(24 * 12)
    values[-30:] = np.nan
    data = _hourly(12, {"sigma_bz_nT": values})
    feature = BzSigma(taus_days=(0.5,), detrend_days=8.0)
    t = data.index[-1] + pd.Timedelta(hours=1)
    assert np.isnan(feature.compute(data, pd.DatetimeIndex([t])).iloc[0, 0])


def test_newell_driver_zero_for_northward_and_scaling() -> None:
    feature = NewellCoupling(taus_days=(1.0,), detrend_days=4.0)
    rows = pd.DataFrame(
        {
            "speed_km_s": [400.0, 400.0, 800.0, np.nan],
            "by_gsm_nT": [0.0, 0.0, 0.0, 1.0],
            "bz_gsm_nT": [5.0, -5.0, -5.0, -5.0],
        }
    )
    d = feature._driver(rows)
    assert d[0] == pytest.approx(0.0)
    assert d[1] == pytest.approx(400 ** (4 / 3) * 5 ** (2 / 3))  # theta = 180 deg
    assert d[2] / d[1] == pytest.approx(2 ** (4 / 3))
    assert np.isnan(d[3])


def test_off_grid_times_rejected() -> None:
    data = _hourly(3, {"pdyn_nPa": np.ones(72)})
    feature = DynamicPressure(taus_days=(0.25,), detrend_days=1.0)
    with pytest.raises(ValueError, match="grid"):
        feature.compute(data, pd.DatetimeIndex([to_utc("2020-01-02T00:30Z")]))
