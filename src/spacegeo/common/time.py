"""UTC time handling.

Every timestamp in spacegeo is timezone-aware UTC. Raw sources are converted
at the edges with :func:`assume_utc`; everywhere else, :func:`to_utc` and
:func:`require_utc_index` fail loudly on naive or non-UTC data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import numpy.typing as npt
import pandas as pd

from spacegeo.common.exceptions import TimeZoneError

UTC = "UTC"

TimestampLike = str | datetime | pd.Timestamp


def _timestamp(value: TimestampLike) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if not isinstance(ts, pd.Timestamp):  # pandas returns NaT for missing values
        raise ValueError(f"Not a valid timestamp: {value!r}.")
    return ts


def duration(
    *, days: float = 0.0, hours: float = 0.0, minutes: float = 0.0, seconds: float = 0.0
) -> pd.Timedelta:
    """Build a non-NaT ``pd.Timedelta``, e.g. ``duration(hours=6)``.

    Use instead of ``pd.Timedelta(...)`` so the result is typed as a
    Timedelta rather than ``Timedelta | NaT``.
    """
    td = pd.Timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
    if not isinstance(td, pd.Timedelta):
        raise ValueError("Duration is NaT.")
    return td


ZERO = duration(seconds=0)


def to_utc(value: TimestampLike) -> pd.Timestamp:
    """Convert a timezone-aware timestamp to UTC.

    Args:
        value: Timestamp-like value carrying an explicit timezone.

    Returns:
        The same instant as a UTC ``pd.Timestamp``.

    Raises:
        TimeZoneError: If ``value`` is naive.
    """
    ts = _timestamp(value)
    if ts.tzinfo is None:
        raise TimeZoneError(f"Naive timestamp {ts!r}; give an explicit offset or use assume_utc.")
    return ts.tz_convert(UTC)


def assume_utc(value: TimestampLike) -> pd.Timestamp:
    """Interpret a naive timestamp as UTC; convert an aware one to UTC.

    Use only when parsing raw sources documented to be in UTC.

    Args:
        value: Timestamp-like value, naive or aware.

    Returns:
        A UTC ``pd.Timestamp``.
    """
    ts = _timestamp(value)
    return ts.tz_localize(UTC) if ts.tzinfo is None else ts.tz_convert(UTC)


def require_utc_index(index: pd.Index) -> pd.DatetimeIndex:
    """Assert that an index is a UTC ``DatetimeIndex``.

    Args:
        index: Index to check.

    Returns:
        The index, typed as ``pd.DatetimeIndex``.

    Raises:
        TimeZoneError: If the index is not datetime-based or not UTC.
    """
    if not isinstance(index, pd.DatetimeIndex):
        raise TimeZoneError(f"Expected a DatetimeIndex, got {type(index).__name__}.")
    if index.tz is None or str(index.tz) != UTC:
        raise TimeZoneError(f"Expected a UTC index, got tz={index.tz!r}.")
    return index


@dataclass(frozen=True)
class TimeWindow:
    """Half-open UTC interval ``[start, end)``.

    Attributes:
        start: Inclusive start, UTC.
        end: Exclusive end, UTC.
    """

    start: pd.Timestamp
    end: pd.Timestamp

    def __post_init__(self) -> None:
        object.__setattr__(self, "start", to_utc(self.start))
        object.__setattr__(self, "end", to_utc(self.end))
        if self.end <= self.start:
            raise ValueError(f"TimeWindow end {self.end} must be after start {self.start}.")

    @property
    def duration(self) -> pd.Timedelta:
        """Length of the window."""
        return self.end - self.start

    def contains(self, ts: TimestampLike) -> bool:
        """Return whether a timestamp falls inside ``[start, end)``."""
        t = to_utc(ts)
        return bool(self.start <= t < self.end)

    def overlaps(self, other: TimeWindow) -> bool:
        """Return whether two windows share any instant."""
        return bool(self.start < other.end and other.start < self.end)

    def mask(self, index: pd.Index) -> npt.NDArray[np.bool_]:
        """Boolean mask selecting index entries inside the window."""
        utc_index = require_utc_index(index)
        return np.asarray((utc_index >= self.start) & (utc_index < self.end), dtype=bool)
