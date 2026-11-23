"""Geodesy helpers: great-circle distances and coordinate normalization."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

EARTH_RADIUS_KM = 6371.0088
"""Mean Earth radius (IUGG), km."""

MAX_ABS_LATITUDE_DEG = 90.0


def normalize_longitude(lon_deg: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """Wrap longitudes into ``[-180, 180)`` degrees."""
    lon = np.asarray(lon_deg, dtype=np.float64)
    return (lon + 180.0) % 360.0 - 180.0


def haversine_km(
    lat1_deg: npt.ArrayLike,
    lon1_deg: npt.ArrayLike,
    lat2_deg: npt.ArrayLike,
    lon2_deg: npt.ArrayLike,
) -> npt.NDArray[np.float64]:
    """Great-circle distance between points, vectorized.

    Args:
        lat1_deg: Latitude(s) of the first point(s), degrees.
        lon1_deg: Longitude(s) of the first point(s), degrees.
        lat2_deg: Latitude(s) of the second point(s), degrees.
        lon2_deg: Longitude(s) of the second point(s), degrees.

    Returns:
        Distance(s) in km, broadcast over the inputs.
    """
    lat1, lon1, lat2, lon2 = (
        np.radians(np.asarray(v, dtype=np.float64))
        for v in (lat1_deg, lon1_deg, lat2_deg, lon2_deg)
    )
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


@dataclass(frozen=True)
class GeoPoint:
    """A point on the Earth's surface.

    Attributes:
        lat_deg: Latitude in [-90, 90] degrees.
        lon_deg: Longitude, normalized to [-180, 180) degrees.
    """

    lat_deg: float
    lon_deg: float

    def __post_init__(self) -> None:
        if abs(self.lat_deg) > MAX_ABS_LATITUDE_DEG:
            raise ValueError(f"Latitude {self.lat_deg} outside [-90, 90].")
        object.__setattr__(self, "lon_deg", float(normalize_longitude(self.lon_deg)))

    def distance_km(self, other: GeoPoint) -> float:
        """Great-circle distance to another point, km."""
        return float(haversine_km(self.lat_deg, self.lon_deg, other.lat_deg, other.lon_deg))


MAX_ABS_LONGITUDE_DEG = 180.0


@dataclass(frozen=True)
class GeoBox:
    """A latitude/longitude box, half-open on its upper edges.

    A box whose ``lon_min_deg`` is greater than ``lon_max_deg`` crosses the
    antimeridian (e.g. ``lon_min_deg=165, lon_max_deg=-150`` covers the
    Aleutians from 165°E across 180° to 150°W).

    Attributes:
        lat_min_deg: Southern edge, degrees (inclusive).
        lat_max_deg: Northern edge, degrees (exclusive).
        lon_min_deg: Western edge, degrees in [-180, 180] (inclusive).
        lon_max_deg: Eastern edge, degrees in [-180, 180] (exclusive).
    """

    lat_min_deg: float
    lat_max_deg: float
    lon_min_deg: float
    lon_max_deg: float

    def __post_init__(self) -> None:
        lats = (self.lat_min_deg, self.lat_max_deg)
        lons = (self.lon_min_deg, self.lon_max_deg)
        if any(abs(v) > MAX_ABS_LATITUDE_DEG for v in lats):
            raise ValueError(f"Latitudes {lats} outside [-90, 90].")
        if any(abs(v) > MAX_ABS_LONGITUDE_DEG for v in lons):
            raise ValueError(f"Longitudes {lons} outside [-180, 180].")
        if self.lat_min_deg >= self.lat_max_deg:
            raise ValueError(
                f"lat_min {self.lat_min_deg} must be below lat_max {self.lat_max_deg}."
            )
        if self.lon_min_deg == self.lon_max_deg:
            raise ValueError("Longitude edges must differ.")

    @property
    def crosses_antimeridian(self) -> bool:
        """Whether the box wraps across 180°."""
        return self.lon_min_deg > self.lon_max_deg

    def contains(self, lat_deg: npt.ArrayLike, lon_deg: npt.ArrayLike) -> npt.NDArray[np.bool_]:
        """Vectorized membership test.

        Args:
            lat_deg: Latitude(s), degrees.
            lon_deg: Longitude(s), degrees (any range; normalized internally).

        Returns:
            Boolean array, broadcast over the inputs.
        """
        lat = np.asarray(lat_deg, dtype=np.float64)
        lon = normalize_longitude(lon_deg)
        in_lat = (lat >= self.lat_min_deg) & (lat < self.lat_max_deg)
        east_of_min = lon >= self.lon_min_deg
        west_of_max = lon < self.lon_max_deg
        in_lon = (
            (east_of_min | west_of_max)
            if self.crosses_antimeridian
            else (east_of_min & west_of_max)
        )
        return np.asarray(in_lat & in_lon, dtype=bool)
