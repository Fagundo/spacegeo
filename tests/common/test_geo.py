import numpy as np
import pytest

from spacegeo.common.geo import (
    GEOMAGNETIC_POLE_DEG,
    GeoBox,
    GeoPoint,
    GeoRegion,
    geomagnetic_latitude_deg,
    haversine_km,
    normalize_longitude,
)


def test_normalize_longitude() -> None:
    assert normalize_longitude([180.0, -180.0, 190.0, -190.0]).tolist() == [
        -180.0,
        -180.0,
        -170.0,
        170.0,
    ]


def test_quarter_meridian() -> None:
    # Equator to pole is a quarter of a great circle.
    assert haversine_km(0, 0, 90, 0) == pytest.approx(np.pi * 6371.0088 / 2)


def test_haversine_vectorizes() -> None:
    out = haversine_km([0, 0], [0, 0], [0, 0], [1, 2])
    assert out.shape == (2,)
    assert out[1] == pytest.approx(2 * out[0])


def test_geopoint_validates_and_measures() -> None:
    with pytest.raises(ValueError, match="Latitude"):
        GeoPoint(91, 0)
    seattle, tokyo = GeoPoint(47.61, -122.33), GeoPoint(35.68, 139.69)
    assert 7600 < seattle.distance_km(tokyo) < 7800
    assert GeoPoint(0, 190).lon_deg == -170.0


def test_geomagnetic_latitude_known_points() -> None:
    pole = geomagnetic_latitude_deg(*GEOMAGNETIC_POLE_DEG)
    assert pole[0] == pytest.approx(90.0)
    # Anchorage ~61N 150W sits near 60-62 degrees geomagnetic; Lima ~12S 77W near +1.
    assert geomagnetic_latitude_deg(61.2, -149.9)[0] == pytest.approx(61.0, abs=2.5)
    assert abs(geomagnetic_latitude_deg(-12.0, -77.0)[0]) < 5


def test_region_centroid_across_antimeridian() -> None:
    region = GeoRegion((GeoBox(50, 56, 170, -170),))
    c = region.centroid
    assert c.lat_deg == pytest.approx(53.0, abs=0.1)
    assert abs(c.lon_deg) == pytest.approx(180.0, abs=0.1)
