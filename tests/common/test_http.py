import urllib.error
from pathlib import Path

import pytest

from spacegeo.common.http import UrllibHttpClient


class _Flaky(UrllibHttpClient):
    def __init__(self, failures: list[Exception]) -> None:
        super().__init__(attempts=3, backoff_s=0.0)
        self.failures = failures
        self.calls = 0

    def _download_once(self, url: str, dest: Path) -> None:
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        dest.write_text("ok")


def _http(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("u", code, "x", None, None)  # type: ignore[arg-type]


def test_retries_resets_then_succeeds(tmp_path: Path) -> None:
    client = _Flaky([ConnectionResetError(), _http(503)])
    client.download("u", tmp_path / "f")
    assert client.calls == 3
    assert (tmp_path / "f").read_text() == "ok"


def test_gives_up_after_attempts(tmp_path: Path) -> None:
    client = _Flaky([ConnectionResetError()] * 3)
    with pytest.raises(ConnectionResetError):
        client.download("u", tmp_path / "f")
    assert client.calls == 3


def test_not_found_is_not_retried(tmp_path: Path) -> None:
    client = _Flaky([_http(404)])
    with pytest.raises(urllib.error.HTTPError):
        client.download("u", tmp_path / "f")
    assert client.calls == 1
