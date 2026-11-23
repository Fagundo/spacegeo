import numpy as np
import pandas as pd
import pytest

from spacegeo.common.exceptions import NotFittedError
from spacegeo.common.geo import GeoBox, GeoRegion
from spacegeo.data.preprocessing.regional_completeness import (
    CompletenessSettings,
    RegionalCompletenessCut,
)

A = GeoRegion((GeoBox(0, 10, 0, 10),))
B = GeoRegion((GeoBox(20, 30, 0, 10),))


def _gr(rng: np.random.Generator, n: int, mc: float) -> np.ndarray:
    """Gutenberg-Richter (b=1) magnitudes, detected with a ramp below ``mc``."""
    mags = 2.0 + rng.exponential(1 / np.log(10), n * 10)
    detect = rng.uniform(size=mags.size) < np.clip((mags - (mc - 0.5)) / 0.5, 0, 1)
    return np.round(mags[detect][:n], 1)


def _catalog(rng: np.random.Generator) -> pd.DataFrame:
    start = pd.Timestamp("2000-01-01", tz="UTC")
    early = _gr(rng, 3000, 3.3)  # 2000-2004: worse network
    late = _gr(rng, 3000, 2.8)  # 2005-2009
    t = np.r_[rng.uniform(0, 5 * 365, early.size), rng.uniform(5 * 365 + 2, 10 * 365, late.size)]
    frame = pd.DataFrame(
        {"lat_deg": 5.0, "lon_deg": 5.0, "mag": np.r_[early, late]},
        index=start + pd.to_timedelta(t, unit="D"),
    )
    sparse = pd.DataFrame(
        {"lat_deg": 25.0, "lon_deg": 5.0, "mag": [3.0, 4.0, 5.0]}, index=frame.index[:3]
    )
    outside = pd.DataFrame({"lat_deg": 50.0, "lon_deg": 5.0, "mag": [6.0]}, index=frame.index[:1])
    return pd.concat([frame, sparse, outside]).sort_index()


def test_uses_worst_block_and_fallback() -> None:
    cut = RegionalCompletenessCut({"a": A, "b": B}, floor=2.5).fit(
        _catalog(np.random.default_rng(0))
    )
    assert cut.mc["a"] == pytest.approx(3.3, abs=0.15)  # complete from 3.3 in the early block
    assert cut.mc["b"] == 4.5  # too few events -> fallback


def test_transform_applies_cut_and_drops_outside() -> None:
    catalog = _catalog(np.random.default_rng(1))
    cut = RegionalCompletenessCut(
        {"a": A, "b": B},
        floor=2.5,
        overrides={"a": 3.0},
        settings=CompletenessSettings(fallback=4.0),
    ).fit(catalog)
    out = cut.transform(catalog)
    assert cut.mc == {"a": 3.0, "b": 4.0}
    assert (out.loc[out["lat_deg"] == 5.0, "mag"] >= 3.0).all()
    assert sorted(out.loc[out["lat_deg"] == 25.0, "mag"]) == [4.0, 5.0]
    assert (out["lat_deg"] != 50.0).all()


def test_floor_applies() -> None:
    rng = np.random.default_rng(2)
    mags = np.round(2.0 + rng.exponential(0.43, 2000), 1)  # complete from 2.0
    idx = pd.Timestamp("2000-01-01", tz="UTC") + pd.to_timedelta(
        rng.uniform(0, 3000, 2000), unit="D"
    )
    catalog = pd.DataFrame({"lat_deg": 5.0, "lon_deg": 5.0, "mag": mags}, index=idx).sort_index()
    assert RegionalCompletenessCut({"a": A}, floor=2.5).fit(catalog).mc["a"] == 2.5


def test_requires_fit() -> None:
    with pytest.raises(NotFittedError):
        RegionalCompletenessCut({"a": A}, floor=2.5).transform(pd.DataFrame())
