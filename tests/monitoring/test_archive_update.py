from collections.abc import Sequence
from pathlib import Path

from spacegeo.common.time import TimeWindow, to_utc
from spacegeo.data.io.catalog_archive import CatalogArchive
from spacegeo.data.io.comcat import ComCatReader
from spacegeo.data.io.gfz_kp import GfzKpReader
from spacegeo.data.io.intermagnet import IntermagnetReader
from spacegeo.data.io.yearly_archive import YearlyArchive
from spacegeo.data.preprocessing.hourly_dbdt import HourlyHorizontalDbDt
from spacegeo.data.scraping.base import DownloadRequest, Scraper
from spacegeo.monitoring.archive_update import ArchiveUpdater, UpdatePolicy

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
    updater = ArchiveUpdater(scraper, ComCatReader(), archive, UpdatePolicy(refresh_years=2))
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
    ArchiveUpdater(scraper, ComCatReader(), archive).update(2025, to_utc("2026-01-01T00:00Z"))
    assert archive.years() == [2025]


class _SharedFileScraper(Scraper):
    """One file covers every year, like the GFZ Kp file."""

    source_name = "shared"

    def __init__(self, raw_dir: Path) -> None:
        super().__init__(raw_dir, client=self)
        self.downloads = 0

    def plan(self, window: TimeWindow) -> Sequence[DownloadRequest]:
        return [DownloadRequest("https://example.org/all.txt", "all.txt")]

    def download(self, url: str, dest: Path) -> None:
        self.downloads += 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(GFZ_FIXTURE.read_text())


GFZ_FIXTURE = Path(__file__).parents[1] / "fixtures" / "gfz_kp" / "Kp_ap_Ap_SN_F107_sample.txt"


def test_shared_file_downloaded_once_and_time_deduplicated(tmp_path: Path) -> None:
    reader = GfzKpReader()
    archive = YearlyArchive(tmp_path / "archive", reader.schema)
    scraper = _SharedFileScraper(tmp_path / "raw")
    updater = ArchiveUpdater(scraper, reader, archive, UpdatePolicy(unique_column=None))
    changed = updater.update(2014, to_utc("2026-11-22T12:00Z"))
    assert scraper.downloads == 1
    assert changed == list(range(2014, 2027))  # empty years are stored too
    assert len(archive.read()) == 8 + 8 + 4  # 2026 clipped at 12:00
    updater.update(2014, to_utc("2026-11-22T12:00Z"))
    assert scraper.downloads == 2  # recent years refreshed, still one download


MINUTE_FIXTURE = Path(__file__).parents[1] / "fixtures" / "intermagnet" / "CMO_sample.csv"


class _MinuteScraper(Scraper):
    source_name = "minutes"

    def __init__(self, raw_dir: Path) -> None:
        super().__init__(raw_dir, client=self)

    def plan(self, window: TimeWindow) -> Sequence[DownloadRequest]:
        return [
            DownloadRequest(
                f"https://example.org/{window.start.year}.csv", f"{window.start.year}.csv"
            )
        ]

    def download(self, url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(MINUTE_FIXTURE.read_text() if "2024" in url else "")


def test_transform_applied_and_raw_discarded(tmp_path: Path) -> None:
    archive = YearlyArchive(tmp_path / "archive", HourlyHorizontalDbDt.OUTPUT_SCHEMA)
    scraper = _MinuteScraper(tmp_path / "raw")
    policy = UpdatePolicy(
        refresh_years=1, unique_column=None, transform=HourlyHorizontalDbDt(), discard_raw=True
    )
    ArchiveUpdater(scraper, IntermagnetReader(), archive, policy).update(
        2023, to_utc("2025-01-01T00:00Z")
    )
    stored = archive.read()
    assert len(stored) == 3  # three hours in 2024, nothing in 2023
    assert stored["n_pairs"].tolist() == [59.0, 57.0, 29.0]
    assert not list((tmp_path / "raw").glob("*.csv"))
