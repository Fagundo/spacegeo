from pathlib import Path

import pytest

from spacegeo.common.time import TimeWindow, to_utc
from spacegeo.data.scraping.intermagnet import IntermagnetInfoScraper, IntermagnetScraper


class _NoNetwork:
    def download(self, url: str, dest: Path) -> None:
        raise AssertionError("plan() must not download")


def test_year_request_url(tmp_path: Path) -> None:
    window = TimeWindow(to_utc("2015-01-01T00:00Z"), to_utc("2016-01-01T00:00Z"))
    (request,) = IntermagnetScraper(tmp_path, "cmo", _NoNetwork()).plan(window)
    assert request.url == (
        "https://imag-data.bgs.ac.uk/GIN_V1/hapi/data?dataset=cmo/best-avail/PT1M/xyzf"
        "&parameters=Field_Vector&start=2015-01-01T00:00:00Z&stop=2016-01-01T00:00:00Z&format=csv"
    )
    assert request.filename == "CMO_20150101T0000_20160101T0000.csv"


def test_requests_longer_than_366_days_rejected(tmp_path: Path) -> None:
    window = TimeWindow(to_utc("2015-01-01T00:00Z"), to_utc("2017-01-01T00:00Z"))
    with pytest.raises(ValueError, match="366 days"):
        IntermagnetScraper(tmp_path, "CMO", _NoNetwork()).plan(window)


def test_info_request(tmp_path: Path) -> None:
    window = TimeWindow(to_utc("2015-01-01T00:00Z"), to_utc("2016-01-01T00:00Z"))
    (request,) = IntermagnetInfoScraper(tmp_path, "SIT", _NoNetwork()).plan(window)
    assert request.url.endswith("/info?dataset=sit/best-avail/PT1M/xyzf")
