import numpy as np
import pytest

from spacegeo.common.geo import GeoBox
from spacegeo.common.stats import benjamini_hochberg
from spacegeo.common.time import TimeWindow, to_utc


def test_box_contains_half_open() -> None:
    box = GeoBox(30, 46, 128, 147)
    lat = np.array([30, 46, 40, 40, 40])
    lon = np.array([140, 140, 128, 147, 200])
    assert box.contains(lat, lon).tolist() == [True, False, True, False, False]


def test_box_across_antimeridian() -> None:
    box = GeoBox(50, 65, 165, -135)
    assert box.crosses_antimeridian
    lon = np.array([170, 179.9, -180, -170, -136, -134, 160])
    assert box.contains(np.full(7, 55.0), lon).tolist() == [
        True,
        True,
        True,
        True,
        True,
        False,
        False,
    ]


@pytest.mark.parametrize("args", [(10, 5, 0, 1), (-91, 0, 0, 1), (0, 1, 0, 181), (0, 1, 20, 20)])
def test_box_rejects_bad_edges(args: tuple[float, float, float, float]) -> None:
    with pytest.raises(ValueError, match=r"lat|Lat|Lon"):
        GeoBox(*args)


def test_bh_matches_hand_calculation() -> None:
    q = benjamini_hochberg([0.01, 0.04, 0.03, 0.5])
    np.testing.assert_allclose(q, [0.04, 0.05333333, 0.05333333, 0.5])


def test_bh_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="NaN"):
        benjamini_hochberg([0.1, np.nan])


def test_calendar_year_and_clip() -> None:
    year = TimeWindow.calendar_year(2026)
    assert year.start == to_utc("2026-01-01T00:00Z")
    assert year.end == to_utc("2027-01-01T00:00Z")
    clipped = year.clip_end(to_utc("2026-11-23T00:00Z"))
    assert clipped is not None
    assert clipped.end == to_utc("2026-11-23T00:00Z")
    assert year.clip_end(to_utc("2026-01-01T00:00Z")) is None
