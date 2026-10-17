"""HTTP transport abstraction so scrapers depend on an interface, not urllib."""

from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path
from typing import Protocol


class HttpClient(Protocol):
    """Downloads a URL to a local file."""

    def download(self, url: str, dest: Path) -> None:
        """Fetch ``url`` and write it to ``dest``."""
        ...


class UrllibHttpClient:
    """Standard-library HTTP client with atomic writes."""

    def __init__(self, timeout_s: float = 120.0, user_agent: str = "spacegeo/0.1") -> None:
        self._timeout_s = timeout_s
        self._user_agent = user_agent

    def download(self, url: str, dest: Path) -> None:
        """Fetch ``url`` to ``dest`` via a temporary file, then rename."""
        request = urllib.request.Request(url, headers={"User-Agent": self._user_agent})
        tmp = dest.with_suffix(dest.suffix + ".part")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with (
            urllib.request.urlopen(request, timeout=self._timeout_s) as response,
            tmp.open("wb") as out,
        ):
            shutil.copyfileobj(response, out)
        tmp.replace(dest)
