from pathlib import Path

from spacegeo.common.time import TimeWindow, to_utc
from spacegeo.data.scraping.intermagnet import IntermagnetInfoScraper, IntermagnetScraper


class _NoNetwork:
    def download(self, url: str, dest: Path) -> None:
        raise AssertionError("plan() must not download")


def test_monthly_requests_cover_window(tmp_path: Path) -> None:
    window = TimeWindow(to_utc("2015-01-01T00:00Z"), to_utc("2016-01-01T00:00Z"))
    plan = IntermagnetScraper(tmp_path, "cmo", _NoNetwork()).plan(window)
    assert len(plan) == 12
    assert plan[0].url == (
        "https://imag-data.bgs.ac.uk/GIN_V1/hapi/data?dataset=cmo/best-avail/PT1M/xyzf"
        "&parameters=Field_Vector&start=2015-01-01T00:00:00Z&stop=2015-02-01T00:00:00Z&format=csv"
    )
    assert plan[-1].filename == "CMO_20151201T0000_20160101T0000.csv"


def test_partial_window_clipped(tmp_path: Path) -> None:
    window = TimeWindow(to_utc("2026-01-01T00:00Z"), to_utc("2026-02-10T12:00Z"))
    plan = IntermagnetScraper(tmp_path, "CMO", _NoNetwork()).plan(window)
    assert [r.filename for r in plan] == [
        "CMO_20260101T0000_20260201T0000.csv",
        "CMO_20260201T0000_20260210T1200.csv",
    ]


def test_info_request(tmp_path: Path) -> None:
    window = TimeWindow(to_utc("2015-01-01T00:00Z"), to_utc("2016-01-01T00:00Z"))
    (request,) = IntermagnetInfoScraper(tmp_path, "SIT", _NoNetwork()).plan(window)
    assert request.url.endswith("/info?dataset=sit/best-avail/PT1M/xyzf")
