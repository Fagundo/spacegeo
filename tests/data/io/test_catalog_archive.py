from pathlib import Path

import pandas as pd
import pytest

from spacegeo.common.time import TimeWindow, to_utc
from spacegeo.data.io.catalog_archive import CatalogArchive
from spacegeo.data.io.comcat import ComCatReader

FIXTURE = Path(__file__).parents[2] / "fixtures" / "comcat" / "sample.csv"


def test_round_trip_and_deterministic_bytes(tmp_path: Path) -> None:
    events = ComCatReader().read([FIXTURE])
    archive = CatalogArchive(tmp_path)
    assert archive.write_year(2026, events, "https://example.org/q")
    first = archive.path(2026).read_bytes()
    assert not archive.write_year(2026, events, "https://example.org/q")  # unchanged -> no write
    assert archive.path(2026).read_bytes() == first
    back = archive.read()
    pd.testing.assert_frame_equal(back, events, check_freq=False)
    assert (
        len(archive.read(TimeWindow(to_utc("2026-11-16T00:00Z"), to_utc("2026-11-17T00:00Z")))) == 1
    )
    assert archive.years() == [2026]
    assert (tmp_path / "PROVENANCE.json").exists()


def test_rejects_events_from_another_year(tmp_path: Path) -> None:
    events = ComCatReader().read([FIXTURE])
    with pytest.raises(ValueError, match="outside 2025"):
        CatalogArchive(tmp_path).write_year(2025, events, "u")


def test_read_empty_archive_fails(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        CatalogArchive(tmp_path).read()
