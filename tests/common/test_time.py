from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from spacegeo.common.exceptions import TimeZoneError
from spacegeo.common.time import TimeWindow, assume_utc, duration, require_utc_index, to_utc


def test_to_utc_rejects_naive() -> None:
    with pytest.raises(TimeZoneError):
        to_utc(datetime(2020, 1, 1))  # noqa: DTZ001


def test_to_utc_converts_offset() -> None:
    assert to_utc("2020-01-01T08:00:00+08:00") == pd.Timestamp("2020-01-01T00:00:00", tz="UTC")


def test_assume_utc_localizes_naive() -> None:
    assert assume_utc("2020-01-01").tz is not None


def test_require_utc_index() -> None:
    with pytest.raises(TimeZoneError):
        require_utc_index(pd.date_range("2020", periods=2, freq="D"))
    with pytest.raises(TimeZoneError):
        require_utc_index(
            pd.date_range("2020", periods=2, freq="D", tz=timezone(timedelta(hours=-8)))
        )
    require_utc_index(pd.date_range("2020", periods=2, freq="D", tz="UTC"))


def test_time_window_is_half_open() -> None:
    w = TimeWindow(to_utc("2020-01-01T00:00Z"), to_utc("2020-01-02T00:00Z"))
    assert w.contains("2020-01-01T00:00Z")
    assert not w.contains("2020-01-02T00:00Z")
    assert w.duration == duration(days=1)


def test_time_window_rejects_inverted() -> None:
    with pytest.raises(ValueError, match="after start"):
        TimeWindow(to_utc("2020-01-02T00:00Z"), to_utc("2020-01-01T00:00Z"))


def test_time_window_mask_and_overlap() -> None:
    w = TimeWindow(to_utc("2020-01-02T00:00Z"), to_utc("2020-01-04T00:00Z"))
    idx = pd.date_range("2020-01-01", periods=5, freq="D", tz="UTC")
    assert w.mask(idx).tolist() == [False, True, True, False, False]
    other = TimeWindow(to_utc("2020-01-04T00:00Z"), to_utc("2020-01-05T00:00Z"))
    assert not w.overlaps(other)
