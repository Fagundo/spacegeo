from collections.abc import Sequence
from pathlib import Path

from spacegeo.common.time import TimeWindow, to_utc
from spacegeo.data.io.catalog_archive import CatalogArchive
from spacegeo.data.io.comcat import ComCatReader
from spacegeo.data.scraping.base import DownloadRequest, Scraper
from spacegeo.monitoring.catalog_update import CatalogUpdater

HEADER = "time,latitude,longitude,depth,mag,magType,id\n"


class _FakeScraper(Scraper):
    source_name = "fake"

    def __init__(self, raw_dir: Path) -> None:
        super().__init__(raw_dir, client=self)
        self.windows: list[TimeWindow] = []

    def plan(self, window: TimeWindow) -> Sequence[DownloadRequest]:
        self.windows.append(window)
        return [DownloadRequest(f"https://example.org/{window.start:%Y}", f"{window.start:%Y}.csv")]

    def download(self, url: str, dest: Path) -> None:
        year = url.rsplit("/", 1)[1]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            HEADER
            + f"{year}-03-01T00:00:00Z,10,20,5,5.0,mb,a{year}\n"
            + f"{year}-03-01T00:00:00Z,10,20,5,5.0,mb,a{year}\n"  # duplicate id
            + f"{year}-06-01T00:00:00Z,11,21,5,4.7,mb,b{year}\n"
        )


def test_fetches_missing_then_refreshes_only_recent_years(tmp_path: Path) -> None:
    archive = CatalogArchive(tmp_path / "archive")
    scraper = _FakeScraper(tmp_path / "raw")
    updater = CatalogUpdater(scraper, ComCatReader(), archive, refresh_years=2)
    as_of = to_utc("2026-04-01T00:00Z")

    changed = updater.update(2023, as_of)
    assert changed == [2023, 2024, 2025, 2026]
    assert len(archive.read()) == 7  # duplicates dropped; 2026 window ends before June
    assert scraper.windows[-1].end == as_of

    scraper.windows.clear()
    assert updater.update(2023, as_of) == []
    assert sorted({w.start.year for w in scraper.windows}) == [2025, 2026]


def test_skips_empty_current_year(tmp_path: Path) -> None:
    archive = CatalogArchive(tmp_path / "archive")
    scraper = _FakeScraper(tmp_path / "raw")
    CatalogUpdater(scraper, ComCatReader(), archive).update(2025, to_utc("2026-01-01T00:00Z"))
    assert archive.years() == [2025]
