"""INTERMAGNET 1-minute observatory data via the BGS Edinburgh GIN HAPI service."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from spacegeo.common.http import HttpClient
from spacegeo.common.time import TimeWindow, to_utc
from spacegeo.data.scraping.base import SCRAPERS, DownloadRequest, Scraper

HAPI_URL = "https://imag-data.bgs.ac.uk/GIN_V1/hapi"
_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _dataset(station: str) -> str:
    """HAPI dataset id: best available (definitive where it exists), 1-minute, XYZF."""
    return f"{station.lower()}/best-avail/PT1M/xyzf"


@SCRAPERS.register("intermagnet")
class IntermagnetScraper(Scraper):
    """Plans 1-minute X/Y/Z downloads for one observatory, one file per calendar month.

    Recent data are revised
    (reported -> definitive), so callers should force-refresh the current year.

    Args:
        raw_dir: Where downloads go.
        station: IAGA observatory code (e.g. ``CMO``).
        client: HTTP client.
    """

    source_name = "intermagnet"

    def __init__(self, raw_dir: Path, station: str, client: HttpClient | None = None) -> None:
        super().__init__(raw_dir, client)
        self._station = station.upper()

    def plan(self, window: TimeWindow) -> Sequence[DownloadRequest]:
        """One HAPI CSV request per calendar month overlapping ``window``.

        Year-long responses (~20 MB) get their connections reset by the
        server; month-long ones (~2 MB) are reliable.
        """
        starts = pd.date_range(window.start.floor("D").replace(day=1), window.end, freq="MS")
        requests = []
        for month_start in starts:
            start = max(to_utc(month_start), window.start)
            stop = min(to_utc(month_start + pd.offsets.MonthBegin(1)), window.end)
            if start < stop:
                requests.append(self._request(start, stop))
        return requests

    def _request(self, start: pd.Timestamp, stop: pd.Timestamp) -> DownloadRequest:
        url = (
            f"{HAPI_URL}/data?dataset={_dataset(self._station)}&parameters=Field_Vector"
            f"&start={start:{_TIME_FORMAT}}&stop={stop:{_TIME_FORMAT}}&format=csv"
        )
        name = f"{self._station}_{start:%Y%m%dT%H%M}_{stop:%Y%m%dT%H%M}.csv"
        return DownloadRequest(url=url, filename=name)


@SCRAPERS.register("intermagnet_info")
class IntermagnetInfoScraper(Scraper):
    """Plans the HAPI ``info`` document (coordinates, parameters, fill values) of a station.

    Args:
        raw_dir: Where downloads go.
        station: IAGA observatory code.
        client: HTTP client.
    """

    source_name = "intermagnet_info"

    def __init__(self, raw_dir: Path, station: str, client: HttpClient | None = None) -> None:
        super().__init__(raw_dir, client)
        self._station = station.upper()

    def plan(self, window: TimeWindow) -> Sequence[DownloadRequest]:
        """The station's info JSON, whatever ``window`` is."""
        del window
        return [
            DownloadRequest(
                url=f"{HAPI_URL}/info?dataset={_dataset(self._station)}",
                filename=f"{self._station}_info.json",
            )
        ]
