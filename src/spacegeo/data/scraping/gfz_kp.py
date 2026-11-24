"""GFZ Potsdam Kp/ap/Ap/SN/F10.7 index file (one file since 1932)."""

from __future__ import annotations

from collections.abc import Sequence

from spacegeo.common.time import TimeWindow
from spacegeo.data.scraping.base import SCRAPERS, DownloadRequest, Scraper


@SCRAPERS.register("gfz_kp")
class GfzKpScraper(Scraper):
    """Plans the single GFZ index file, which covers every window.

    The file is rewritten daily (nowcast values, then definitive ones), so
    callers refreshing recent data should force a download.
    """

    source_name = "gfz_kp"
    URL = "https://kp.gfz.de/app/files/Kp_ap_Ap_SN_F107_since_1932.txt"

    def plan(self, window: TimeWindow) -> Sequence[DownloadRequest]:
        """The one file, whatever ``window`` is."""
        del window
        return [DownloadRequest(url=self.URL, filename="Kp_ap_Ap_SN_F107_since_1932.txt")]
