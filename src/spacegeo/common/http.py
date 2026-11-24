"""HTTP transport abstraction so scrapers depend on an interface, not urllib."""

from __future__ import annotations

import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol

from spacegeo.common.log import get_logger

_log = get_logger(__name__)
_RETRY_STATUS = frozenset({400, 429, 500, 502, 503, 504})
"""HTTP statuses retried; 400 included because some data services return it transiently."""


class HttpClient(Protocol):
    """Downloads a URL to a local file."""

    def download(self, url: str, dest: Path) -> None:
        """Fetch ``url`` and write it to ``dest``."""
        ...


class UrllibHttpClient:
    """Standard-library HTTP client with atomic writes and retries.

    Connection resets, timeouts and transient HTTP statuses are retried with
    exponential backoff; the last error is raised if every attempt fails.

    Args:
        timeout_s: Socket timeout per operation, seconds.
        user_agent: User-Agent header.
        attempts: Total tries per download.
        backoff_s: Wait before the second try, seconds; doubles each time.
    """

    def __init__(
        self,
        timeout_s: float = 120.0,
        user_agent: str = "spacegeo/0.1",
        attempts: int = 4,
        backoff_s: float = 10.0,
    ) -> None:
        self._timeout_s = timeout_s
        self._user_agent = user_agent
        self._attempts = attempts
        self._backoff_s = backoff_s

    def download(self, url: str, dest: Path) -> None:
        """Fetch ``url`` to ``dest`` via a temporary file, then rename."""
        for attempt in range(1, self._attempts + 1):
            try:
                self._download_once(url, dest)
                return
            except (urllib.error.URLError, ConnectionError, TimeoutError) as err:
                if attempt == self._attempts or not self._retryable(err):
                    raise
                wait = self._backoff_s * 2 ** (attempt - 1)
                _log.warning("Download failed (%s); retry %d in %.0f s", err, attempt, wait)
                time.sleep(wait)

    @staticmethod
    def _retryable(err: Exception) -> bool:
        if isinstance(err, urllib.error.HTTPError):
            return err.code in _RETRY_STATUS
        return True

    def _download_once(self, url: str, dest: Path) -> None:
        request = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
        tmp = dest.with_suffix(dest.suffix + ".part")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with (
            urllib.request.urlopen(request, timeout=self._timeout_s) as response,
            tmp.open("wb") as out,
        ):
            shutil.copyfileobj(response, out)
        tmp.replace(dest)
