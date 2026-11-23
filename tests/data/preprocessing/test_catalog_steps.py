import numpy as np
import pandas as pd
import pytest

from spacegeo.data.preprocessing.gardner_knopoff import GardnerKnopoffDeclusterer
from spacegeo.data.preprocessing.magnitude_cut import MagnitudeCut


def _catalog(rows: list[tuple[str, float, float, float]]) -> pd.DataFrame:
    index = pd.DatetimeIndex([pd.Timestamp(r[0], tz="UTC") for r in rows])
    return pd.DataFrame(
        {
            "lat_deg": [r[1] for r in rows],
            "lon_deg": [r[2] for r in rows],
            "mag": [r[3] for r in rows],
        },
        index=index,
    )


def test_magnitude_cut_drops_small_and_missing() -> None:
    cat = _catalog(
        [("2020-01-01", 0, 0, 4.4), ("2020-01-02", 0, 0, 4.5), ("2020-01-03", 0, 0, np.nan)]
    )
    out = MagnitudeCut(4.5).transform(cat)
    assert out["mag"].tolist() == [4.5]


def test_windows_match_published_values() -> None:
    gk = GardnerKnopoffDeclusterer
    # Gardner & Knopoff (1974) table: M5 -> 40 km / 155 d, M7 -> 70 km / 915 d.
    np.testing.assert_allclose(gk.distance_window_km([5.0, 7.0]), [40.0, 70.0], rtol=0.02)
    np.testing.assert_allclose(gk.time_window_days([5.0, 7.0]), [155.0, 915.0], rtol=0.08)


def test_aftershocks_removed_distant_event_kept() -> None:
    cat = _catalog(
        [
            ("2020-01-01", 0.0, 0.0, 4.6),  # foreshock, 1 day before, 10 km away
            ("2020-01-02", 0.05, 0.05, 7.0),  # mainshock
            ("2020-01-10", 0.1, 0.0, 5.5),  # aftershock
            ("2020-01-10", 30.0, 30.0, 5.0),  # unrelated, far away
            ("2025-01-01", 0.0, 0.0, 5.0),  # same place, long after the window
        ]
    )
    out = GardnerKnopoffDeclusterer().transform(cat)
    assert out["mag"].tolist() == [7.0, 5.0, 5.0]
    kept_foreshock = GardnerKnopoffDeclusterer(include_foreshocks=False).transform(cat)
    assert kept_foreshock["mag"].tolist() == [4.6, 7.0, 5.0, 5.0]


def test_decluster_requires_magnitudes() -> None:
    cat = _catalog([("2020-01-01", 0, 0, np.nan)])
    with pytest.raises(ValueError, match="cut first"):
        GardnerKnopoffDeclusterer().transform(cat)
