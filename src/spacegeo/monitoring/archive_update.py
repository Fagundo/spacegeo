"""Bring a committed yearly archive up to date from its source."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from spacegeo.common.log import get_logger
from spacegeo.common.time import TimeWindow, to_utc
from spacegeo.data.io.base import DatasetReader
from spacegeo.data.io.yearly_archive import YearlyArchive
from spacegeo.data.preprocessing.base import Preprocessor
from spacegeo.data.scraping.base import Scraper

_log = get_logger(__name__)


@dataclass(frozen=True)
class UpdatePolicy:
    """How an :class:`ArchiveUpdater` refreshes, deduplicates and transforms.

    Attributes:
        refresh_years: How many of the most recent years to always refresh.
        unique_column: Column identifying a row (e.g. ``event_id``); later
            duplicates win. ``None`` deduplicates on the timestamp instead.
        transform: Optional stateless step applied to the parsed rows before
            storing (e.g. 1-minute field -> hourly dB/dt).
        discard_raw: Delete raw files once their year is stored (for sources
            too large to keep on a CI runner).
    """

    refresh_years: int = 2
    unique_column: str | None = "event_id"
    transform: Preprocessor | None = None
    discard_raw: bool = False


class ArchiveUpdater:
    """Downloads missing years and re-downloads recent ones.

    Sources are revised after the fact (catalog relocations, OMNI and Kp
    going from provisional to definitive), so the last ``refresh_years``
    years (including the current, partial one) are always fetched again;
    older years are fetched only if missing. A file that several years share
    (e.g. one index file since 1932) is downloaded once per update.

    Args:
        scraper: Source of raw files.
        reader: Parser for those files.
        archive: Where parsed years are stored.
        policy: Refresh, deduplication and transform settings.
    """

    def __init__(
        self,
        scraper: Scraper,
        reader: DatasetReader,
        archive: YearlyArchive,
        policy: UpdatePolicy | None = None,
    ) -> None:
        self._scraper = scraper
        self._reader = reader
        self._archive = archive
        self._policy = policy or UpdatePolicy()
        self._fetched_urls: set[str] = set()

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
        self._fetched_urls.clear()
        changed: list[int] = []
        for year in range(first_year, stop.year + 1):
            recent = year > stop.year - self._policy.refresh_years
            window = TimeWindow.calendar_year(year).clip_end(stop)
            if window is None or (year in stored and not recent):
                continue
            if self._fetch(year, window):
                changed.append(year)
        _log.info("Archive years changed: %s", changed or "none")
        return changed

    def _fetch(self, year: int, window: TimeWindow) -> bool:
        urls = [request.url for request in self._scraper.plan(window)]
        force = not self._fetched_urls.issuperset(urls)
        paths = self._scraper.scrape(window, force=force)
        self._fetched_urls.update(urls)
        rows = self._deduplicate(self._reader.read(paths))
        if self._policy.transform is not None:
            rows = self._policy.transform.fit_transform(rows)
        rows = rows.loc[window.mask(rows.index)]
        changed = self._archive.write_year(year, rows, urls[0])
        if self._policy.discard_raw:
            for path in paths:
                path.unlink()
        return changed

    def _deduplicate(self, rows: pd.DataFrame) -> pd.DataFrame:
        if self._policy.unique_column is None:
            return rows.loc[~rows.index.duplicated(keep="last")]
        return rows.loc[~rows[self._policy.unique_column].duplicated(keep="last")]
