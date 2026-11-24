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


def destination_point(
    lat_deg: npt.ArrayLike,
    lon_deg: npt.ArrayLike,
    bearing_rad: npt.ArrayLike,
    distance_km: npt.ArrayLike,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Point reached by travelling a great-circle distance on a bearing.

    Args:
        lat_deg: Start latitude(s), degrees.
        lon_deg: Start longitude(s), degrees.
        bearing_rad: Initial bearing(s), radians clockwise from north.
        distance_km: Distance(s), km.

    Returns:
        ``(lat_deg, lon_deg)`` arrays broadcast over the inputs; longitude
        normalized to [-180, 180).
    """
    lat1 = np.radians(np.asarray(lat_deg, dtype=np.float64))
    lon1 = np.radians(np.asarray(lon_deg, dtype=np.float64))
    theta = np.asarray(bearing_rad, dtype=np.float64)
    delta = np.asarray(distance_km, dtype=np.float64) / EARTH_RADIUS_KM
    sin_lat2 = np.sin(lat1) * np.cos(delta) + np.cos(lat1) * np.sin(delta) * np.cos(theta)
    lat2 = np.arcsin(np.clip(sin_lat2, -1.0, 1.0))
    lon2 = lon1 + np.arctan2(
        np.sin(theta) * np.sin(delta) * np.cos(lat1), np.cos(delta) - np.sin(lat1) * sin_lat2
    )
    return np.degrees(lat2), normalize_longitude(np.degrees(lon2))


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

GEOMAGNETIC_POLE_DEG = (80.65, -72.68)
"""Northern geomagnetic (centred-dipole) pole, IGRF-13 epoch 2020: (lat, lon)."""


def unit_vectors(lat_deg: npt.ArrayLike, lon_deg: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """Earth-centred unit vectors, shape ``(n, 3)``, for points in degrees."""
    lat = np.radians(np.atleast_1d(np.asarray(lat_deg, dtype=np.float64)))
    lon = np.radians(np.atleast_1d(np.asarray(lon_deg, dtype=np.float64)))
    return np.column_stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])


def geomagnetic_latitude_deg(
    lat_deg: npt.ArrayLike, lon_deg: npt.ArrayLike
) -> npt.NDArray[np.float64]:
    """Centred-dipole geomagnetic latitude, degrees (IGRF-13 2020 pole).

    Args:
        lat_deg: Geographic latitude(s), degrees.
        lon_deg: Geographic longitude(s), degrees.

    Returns:
        90 degrees minus the angular distance to :data:`GEOMAGNETIC_POLE_DEG`.
    """
    pole = unit_vectors(*GEOMAGNETIC_POLE_DEG)[0]
    cos_angle = np.clip(unit_vectors(lat_deg, lon_deg) @ pole, -1.0, 1.0)
    return 90.0 - np.degrees(np.arccos(cos_angle))


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
    def lon_span_deg(self) -> float:
        """Width in longitude, degrees (handles the antimeridian)."""
        return (self.lon_max_deg - self.lon_min_deg) % 360.0 or 360.0

    @property
    def area_km2(self) -> float:
        """Area on the sphere, km^2."""
        sin_band = np.sin(np.radians(self.lat_max_deg)) - np.sin(np.radians(self.lat_min_deg))
        return float(EARTH_RADIUS_KM**2 * np.radians(self.lon_span_deg) * sin_band)

    def sample(self, n: int, rng: np.random.Generator) -> tuple[npt.NDArray[np.float64], ...]:
        """``n`` points uniform over the box's area on the sphere: ``(lat, lon)``."""
        sin_lo, sin_hi = np.sin(np.radians([self.lat_min_deg, self.lat_max_deg]))
        lat = np.degrees(np.arcsin(rng.uniform(sin_lo, sin_hi, n)))
        lon = normalize_longitude(self.lon_min_deg + rng.uniform(0.0, self.lon_span_deg, n))
        return lat, lon

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


def _lon_intervals(box: GeoBox) -> list[tuple[float, float]]:
    if box.crosses_antimeridian:
        return [(box.lon_min_deg, 180.0), (-180.0, box.lon_max_deg)]
    return [(box.lon_min_deg, box.lon_max_deg)]


def boxes_intersect(a: GeoBox, b: GeoBox) -> bool:
    """Whether two half-open boxes share any area (touching edges do not count).

    Args:
        a: First box.
        b: Second box.

    Returns:
        True if some point lies inside both.
    """
    if not (a.lat_min_deg < b.lat_max_deg and b.lat_min_deg < a.lat_max_deg):
        return False
    return any(
        lo_a < hi_b and lo_b < hi_a
        for lo_a, hi_a in _lon_intervals(a)
        for lo_b, hi_b in _lon_intervals(b)
    )


@dataclass(frozen=True)
class GeoRegion:
    """A union of :class:`GeoBox` pieces (e.g. an L-shaped plate boundary).

    Attributes:
        boxes: The pieces; they may share edges but should not overlap.
    """

    boxes: tuple[GeoBox, ...]

    def __post_init__(self) -> None:
        if not self.boxes:
            raise ValueError("A region needs at least one box.")

    def contains(self, lat_deg: npt.ArrayLike, lon_deg: npt.ArrayLike) -> npt.NDArray[np.bool_]:
        """Vectorized membership test (inside any piece)."""
        masks = [box.contains(lat_deg, lon_deg) for box in self.boxes]
        return np.asarray(np.logical_or.reduce(masks), dtype=bool)

    def intersects(self, other: GeoRegion) -> bool:
        """Whether this region shares any area with ``other``."""
        return any(boxes_intersect(a, b) for a in self.boxes for b in other.boxes)

    @property
    def area_km2(self) -> float:
        """Total area, km^2 (pieces are assumed not to overlap)."""
        return sum(box.area_km2 for box in self.boxes)

    @property
    def centroid(self) -> GeoPoint:
        """Area-weighted centre of the pieces' centres (on the sphere, so 180° safe)."""
        lat = [(b.lat_min_deg + b.lat_max_deg) / 2 for b in self.boxes]
        lon = [b.lon_min_deg + b.lon_span_deg / 2 for b in self.boxes]
        weights = np.array([b.area_km2 for b in self.boxes])
        x, y, z = (unit_vectors(lat, lon) * weights[:, None]).sum(axis=0)
        lat_c = float(np.degrees(np.arctan2(z, np.hypot(x, y))))
        return GeoPoint(lat_c, float(np.degrees(np.arctan2(y, x))))

    def sample(self, n: int, rng: np.random.Generator) -> tuple[npt.NDArray[np.float64], ...]:
        """``n`` points uniform over the region's area: ``(lat, lon)``."""
        areas = np.array([box.area_km2 for box in self.boxes])
        counts = rng.multinomial(n, areas / areas.sum())
        pieces = [box.sample(int(k), rng) for box, k in zip(self.boxes, counts, strict=True)]
        return np.concatenate([p[0] for p in pieces]), np.concatenate([p[1] for p in pieces])

    def exit_distances_km(
        self,
        lat_deg: npt.ArrayLike,
        lon_deg: npt.ArrayLike,
        bearings_rad: npt.ArrayLike,
        max_km: float,
        step_km: float = 5.0,
    ) -> npt.NDArray[np.float64]:
        """Distance along each bearing at which a point first leaves the region.

        Found by marching outward in ``step_km`` steps (accuracy about half a
        step) and capped at ``max_km``.

        Args:
            lat_deg: Start latitudes, shape ``(n,)``.
            lon_deg: Start longitudes, shape ``(n,)``.
            bearings_rad: Bearings, shape ``(k,)``.
            max_km: Cap, km.
            step_km: March step, km.

        Returns:
            Array of shape ``(n, k)``, km.
        """
        lat = np.asarray(lat_deg, dtype=np.float64)
        lon = np.asarray(lon_deg, dtype=np.float64)
        theta = np.asarray(bearings_rad, dtype=np.float64)
        radii = np.arange(step_km, max_km + step_km, step_km)
        chunk = 512
        parts = [
            self._exit_chunk(lat[i : i + chunk], lon[i : i + chunk], theta, radii, step_km)
            for i in range(0, lat.size, chunk)
        ]
        out = np.concatenate(parts) if parts else np.empty((0, theta.size))
        return np.minimum(out, max_km)

    def _exit_chunk(
        self,
        lat: npt.NDArray[np.float64],
        lon: npt.NDArray[np.float64],
        theta: npt.NDArray[np.float64],
        radii: npt.NDArray[np.float64],
        step_km: float,
    ) -> npt.NDArray[np.float64]:
        lat2, lon2 = destination_point(
            lat[:, None, None], lon[:, None, None], theta[None, :, None], radii[None, None, :]
        )
        outside = ~self.contains(lat2, lon2)
        first = np.where(outside.any(axis=2), outside.argmax(axis=2), radii.size)
        return np.where(first < radii.size, (first + 0.5) * step_km, np.inf)
