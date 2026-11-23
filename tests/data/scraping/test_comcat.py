from pathlib import Path
from urllib.parse import parse_qs, urlparse

from spacegeo.common.geo import GeoBox
from spacegeo.common.time import TimeWindow, to_utc
from spacegeo.data.scraping.base import SCRAPERS
from spacegeo.data.scraping.comcat import ComCatScraper


class _NoNetwork:
    def download(self, url: str, dest: Path) -> None:
        raise AssertionError("plan() must not download")


def _scraper(tmp_path: Path) -> ComCatScraper:
    return ComCatScraper(tmp_path, client=_NoNetwork(), min_magnitude=4.5)


def test_plan_splits_by_calendar_year(tmp_path: Path) -> None:
    window = TimeWindow(to_utc("2024-06-01T00:00Z"), to_utc("2026-11-23T00:00Z"))
    plan = _scraper(tmp_path).plan(window)
    queries = [parse_qs(urlparse(r.url).query) for r in plan]
    assert [q["starttime"][0] for q in queries] == [
        "2024-06-01T00:00:00",
        "2025-01-01T00:00:00",
        "2026-01-01T00:00:00",
    ]
    assert [q["endtime"][0] for q in queries] == [
        "2025-01-01T00:00:00",
        "2026-01-01T00:00:00",
        "2026-11-23T00:00:00",
    ]
    assert all(q["minmagnitude"] == ["4.5"] and q["eventtype"] == ["earthquake"] for q in queries)


def test_completed_years_have_stable_names(tmp_path: Path) -> None:
    early = TimeWindow(to_utc("2025-01-01T00:00Z"), to_utc("2026-11-16T00:00Z"))
    late = TimeWindow(to_utc("2025-01-01T00:00Z"), to_utc("2026-11-23T00:00Z"))
    a, b = (_scraper(tmp_path).plan(w) for w in (early, late))
    assert a[0].filename == b[0].filename
    assert a[-1].filename != b[-1].filename


def test_single_chunk_inside_one_year(tmp_path: Path) -> None:
    window = TimeWindow(to_utc("2026-11-16T00:00Z"), to_utc("2026-11-23T00:00Z"))
    assert len(_scraper(tmp_path).plan(window)) == 1


def test_registered() -> None:
    assert SCRAPERS.get("comcat") is ComCatScraper


def test_monthly_chunks(tmp_path: Path) -> None:
    scraper = ComCatScraper(tmp_path, client=_NoNetwork(), min_magnitude=2.5, chunk="MS")
    plan = scraper.plan(TimeWindow(to_utc("2026-01-01T00:00Z"), to_utc("2026-03-15T00:00Z")))
    starts = [parse_qs(urlparse(r.url).query)["starttime"][0] for r in plan]
    assert starts == ["2026-01-01T00:00:00", "2026-02-01T00:00:00", "2026-03-01T00:00:00"]
    assert all("minmagnitude=2.5" in r.url for r in plan)


def test_box_queries_one_request_per_box_and_chunk(tmp_path: Path) -> None:
    boxes = [GeoBox(50, 65, 165, -135), GeoBox(30, 39, -126, -114)]
    scraper = ComCatScraper(
        tmp_path, client=_NoNetwork(), min_magnitude=2.5, chunk="QS", bounds=boxes
    )
    plan = scraper.plan(TimeWindow(to_utc("2025-01-01T00:00Z"), to_utc("2025-07-01T00:00Z")))
    assert len(plan) == 4
    first = parse_qs(urlparse(plan[0].url).query)
    assert (first["minlongitude"], first["maxlongitude"]) == (["165"], ["225"])
    second = parse_qs(urlparse(plan[1].url).query)
    assert (second["minlatitude"], second["maxlongitude"]) == (["30"], ["-114"])
    assert len({r.filename for r in plan}) == 4
