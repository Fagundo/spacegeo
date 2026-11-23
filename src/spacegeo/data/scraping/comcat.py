"""USGS ComCat earthquake catalog via the FDSN event web service."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

from spacegeo.common.geo import GeoBox
from spacegeo.common.http import HttpClient
from spacegeo.common.time import TimeWindow
from spacegeo.data.scraping.base import SCRAPERS, DownloadRequest, Scraper

_ISO = "%Y-%m-%dT%H:%M:%S"


@SCRAPERS.register("comcat")
class ComCatScraper(Scraper):
    """Plans chunked CSV queries against the USGS FDSN event service.

    Completed chunks get a stable file name, so reruns skip them. The last,
    partial chunk is named by its end date, so a later run fetches a fresh
    copy that includes recent events and revisions.

    Args:
        raw_dir: Directory for raw CSV files.
        client: HTTP transport.
        min_magnitude: Lower magnitude bound passed to the service (any
            magnitude type, as reported by ComCat).
        chunk: Pandas frequency of the query chunks; use ``QS`` or ``MS``
            below about M4, where a year can exceed the per-query limit.
        bounds: Optional boxes to restrict the query to; one request per
            box and chunk. ``None`` = global.
    """

    source_name = "comcat"
    BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    MAX_EVENTS_PER_QUERY = 20000
    """Service limit; global M>=4.5 runs ~7-9k events per year."""

    def __init__(
        self,
        raw_dir: Path,
        client: HttpClient | None = None,
        min_magnitude: float = 4.5,
        chunk: str = "YS",
        bounds: Sequence[GeoBox] | None = None,
    ) -> None:
        super().__init__(raw_dir, client)
        self._min_magnitude = min_magnitude
        self._chunk = chunk
        self._bounds: tuple[GeoBox | None, ...] = tuple(bounds) if bounds else (None,)

    def plan(self, window: TimeWindow) -> Sequence[DownloadRequest]:
        """One request per chunk (calendar year by default) and box overlapping ``window``."""
        return [
            self._request(start, end, i, box)
            for start, end in self._chunks(window)
            for i, box in enumerate(self._bounds)
        ]

    def _chunks(self, window: TimeWindow) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
        starts = pd.date_range(window.start.normalize(), window.end, freq=self._chunk, tz="UTC")
        edges = sorted({window.start, *[s for s in starts if window.start < s < window.end]})
        edges.append(window.end)
        return list(pairwise(edges))

    def _request(
        self, start: pd.Timestamp, end: pd.Timestamp, piece: int, box: GeoBox | None
    ) -> DownloadRequest:
        params: dict[str, str | int] = {
            "format": "csv",
            "eventtype": "earthquake",
            "orderby": "time-asc",
            "starttime": start.strftime(_ISO),
            "endtime": end.strftime(_ISO),
            "minmagnitude": f"{self._min_magnitude:g}",
            "limit": self.MAX_EVENTS_PER_QUERY,
        }
        tag = ""
        if box is not None:
            params.update(self._box_params(box))
            tag = f"_box{piece}"
        query = urlencode(params)
        filename = f"comcat_M{self._min_magnitude:g}{tag}_{start:%Y%m%dT%H%M}_{end:%Y%m%dT%H%M}.csv"
        return DownloadRequest(url=f"{self.BASE_URL}?{query}", filename=filename)

    @staticmethod
    def _box_params(box: GeoBox) -> dict[str, str | int]:
        """FDSN bounds; a box across 180 degrees uses an east edge above 180 (allowed to 360)."""
        east = box.lon_max_deg + 360 if box.crosses_antimeridian else box.lon_max_deg
        return {
            "minlatitude": f"{box.lat_min_deg:g}",
            "maxlatitude": f"{box.lat_max_deg:g}",
            "minlongitude": f"{box.lon_min_deg:g}",
            "maxlongitude": f"{east:g}",
        }
