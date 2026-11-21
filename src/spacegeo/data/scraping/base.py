"""Scraper interface.

A scraper decides *what* to download (:meth:`Scraper.plan`); the base class
handles *how*: skipping files that are already current, downloading through
an injected :class:`~spacegeo.common.http.HttpClient`, and recording
provenance.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from spacegeo.common.http import HttpClient, UrllibHttpClient
from spacegeo.common.log import get_logger
from spacegeo.common.provenance import ProvenanceLog
from spacegeo.common.registry import Registry
from spacegeo.common.time import TimeWindow

_log = get_logger(__name__)


@dataclass(frozen=True)
class DownloadRequest:
    """One file to fetch.

    Attributes:
        url: Source URL.
        filename: Local file name inside the source's raw directory.
    """

    url: str
    filename: str


class Scraper(ABC):
    """Downloads one data source into its raw directory.

    Subclasses set :attr:`source_name` and implement :meth:`plan`.
    """

    source_name: ClassVar[str]

    def __init__(self, raw_dir: Path, client: HttpClient | None = None) -> None:
        self._raw_dir = raw_dir
        self._client = client or UrllibHttpClient()
        self._provenance = ProvenanceLog(raw_dir)

    @property
    def raw_dir(self) -> Path:
        """Directory this scraper writes to."""
        return self._raw_dir

    @abstractmethod
    def plan(self, window: TimeWindow) -> Sequence[DownloadRequest]:
        """List the files needed to cover ``window``."""

    def scrape(self, window: TimeWindow, *, force: bool = False) -> list[Path]:
        """Download every planned file that is missing or changed.

        Args:
            window: Period the data should cover.
            force: Re-download even if the local copy is current.

        Returns:
            Paths to the local files, in plan order.
        """
        paths: list[Path] = []
        for request in self.plan(window):
            dest = self._raw_dir / request.filename
            if force or not self._provenance.is_current(dest):
                _log.info("Downloading %s -> %s", request.url, dest)
                self._client.download(request.url, dest)
                self._provenance.record(request.url, dest)
            paths.append(dest)
        return paths


SCRAPERS: Registry[Scraper] = Registry("scraper")
