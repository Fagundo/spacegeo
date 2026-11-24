"""NASA/GSFC OMNI2 hourly solar wind and geomagnetic indices (yearly files)."""

from __future__ import annotations

from collections.abc import Sequence

from spacegeo.common.time import TimeWindow, duration
from spacegeo.data.scraping.base import SCRAPERS, DownloadRequest, Scraper


@SCRAPERS.register("omni2")
class OmniScraper(Scraper):
    """Plans one ``omni2_YYYY.dat`` download per calendar year in the window.

    OMNI2 files are re-issued as new data arrive and older values are
    revised, so callers should force-refresh recent years.
    """

    source_name = "omni2"
    BASE_URL = "https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni"

    def plan(self, window: TimeWindow) -> Sequence[DownloadRequest]:
        """One request per calendar year overlapping ``window`` (end exclusive)."""
        last = (window.end - duration(seconds=1)).year
        return [
            DownloadRequest(url=f"{self.BASE_URL}/omni2_{year}.dat", filename=f"omni2_{year}.dat")
            for year in range(window.start.year, last + 1)
        ]
