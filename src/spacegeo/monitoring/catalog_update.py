"""Bring the committed catalog archive up to date from the source."""

from __future__ import annotations

import pandas as pd

from spacegeo.common.log import get_logger
from spacegeo.common.time import TimeWindow, to_utc
from spacegeo.data.io.base import DatasetReader
from spacegeo.data.io.catalog_archive import CatalogArchive
from spacegeo.data.scraping.base import Scraper

_log = get_logger(__name__)


class CatalogUpdater:
    """Downloads missing years and re-downloads recent ones.

    Catalogs are revised for weeks after an event, so the last
    ``refresh_years`` years (including the current, partial one) are always
    fetched again; older years are fetched only if missing.

    Args:
        scraper: Source of raw files.
        reader: Parser for those files.
        archive: Where parsed years are stored.
        refresh_years: How many of the most recent years to always refresh.
    """

    def __init__(
        self,
        scraper: Scraper,
        reader: DatasetReader,
        archive: CatalogArchive,
        refresh_years: int = 2,
    ) -> None:
        self._scraper = scraper
        self._reader = reader
        self._archive = archive
        self._refresh_years = refresh_years

    def update(self, first_year: int, as_of: pd.Timestamp) -> list[int]:
        """Update every year from ``first_year`` through ``as_of``.

        Args:
            first_year: Earliest year to keep in the archive.
            as_of: Data are fetched up to this UTC instant (exclusive).

        Returns:
            Years whose stored file changed.
        """
        stop = to_utc(as_of)
        stored = set(self._archive.years())
        changed: list[int] = []
        for year in range(first_year, stop.year + 1):
            recent = year > stop.year - self._refresh_years
            window = TimeWindow.calendar_year(year).clip_end(stop)
            if window is None or (year in stored and not recent):
                continue
            if self._fetch(year, window):
                changed.append(year)
        _log.info("Catalog years changed: %s", changed or "none")
        return changed

    def _fetch(self, year: int, window: TimeWindow) -> bool:
        requests = self._scraper.plan(window)
        paths = self._scraper.scrape(window, force=True)
        events = self._reader.read(paths)
        events = events.loc[~events["event_id"].duplicated(keep="last")]
        events = events.loc[window.mask(events.index)]
        return self._archive.write_year(year, events, requests[0].url)
