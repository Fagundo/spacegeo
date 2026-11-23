"""USGS ComCat earthquake catalog via the FDSN event web service."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

from spacegeo.common.http import HttpClient
from spacegeo.common.time import TimeWindow
from spacegeo.data.scraping.base import SCRAPERS, DownloadRequest, Scraper

_ISO = "%Y-%m-%dT%H:%M:%S"


@SCRAPERS.register("comcat")
class ComCatScraper(Scraper):
    """Plans yearly CSV queries against the USGS FDSN event service.

    Completed years get a stable file name, so reruns skip them. The last,
    partial chunk is named by its end date, so a later run fetches a fresh
    copy that includes recent events and revisions.

    Args:
        raw_dir: Directory for raw CSV files.
        client: HTTP transport.
        min_magnitude: Lower magnitude bound passed to the service (any
            magnitude type, as reported by ComCat).
    """

    source_name = "comcat"
    BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    MAX_EVENTS_PER_QUERY = 20000
    """Service limit; global M>=4.5 runs ~7-9k events per year."""

    def __init__(
        self, raw_dir: Path, client: HttpClient | None = None, min_magnitude: float = 4.5
    ) -> None:
        super().__init__(raw_dir, client)
        self._min_magnitude = min_magnitude

    def plan(self, window: TimeWindow) -> Sequence[DownloadRequest]:
        """One request per calendar year overlapping ``window``."""
        return [self._request(start, end) for start, end in self._chunks(window)]

    def _chunks(self, window: TimeWindow) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
        years = pd.date_range(window.start.normalize(), window.end, freq="YS", tz="UTC")
        edges = sorted({window.start, *[y for y in years if window.start < y < window.end]})
        edges.append(window.end)
        return list(pairwise(edges))

    def _request(self, start: pd.Timestamp, end: pd.Timestamp) -> DownloadRequest:
        query = urlencode(
            {
                "format": "csv",
                "eventtype": "earthquake",
                "orderby": "time-asc",
                "starttime": start.strftime(_ISO),
                "endtime": end.strftime(_ISO),
                "minmagnitude": f"{self._min_magnitude:g}",
                "limit": self.MAX_EVENTS_PER_QUERY,
            }
        )
        filename = f"comcat_M{self._min_magnitude:g}_{start:%Y%m%dT%H%M}_{end:%Y%m%dT%H%M}.csv"
        return DownloadRequest(url=f"{self.BASE_URL}?{query}", filename=filename)
