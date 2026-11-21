from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

import pandas as pd
import pytest

from spacegeo.common.exceptions import NotFittedError
from spacegeo.common.time import TimeWindow, to_utc
from spacegeo.common.validation import ColumnSpec, TableSchema
from spacegeo.data.io.base import DatasetReader
from spacegeo.data.preprocessing.base import PreprocessingPipeline, Preprocessor
from spacegeo.data.scraping.base import DownloadRequest, Scraper

WINDOW = TimeWindow(to_utc("2020-01-01T00:00Z"), to_utc("2020-01-03T00:00Z"))


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def download(self, url: str, dest: Path) -> None:
        self.calls.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(url)


class _DailyScraper(Scraper):
    source_name = "fake"

    def plan(self, window: TimeWindow) -> Sequence[DownloadRequest]:
        days = pd.date_range(window.start, window.end, freq="D", inclusive="left")
        return [DownloadRequest(f"https://example.org/{d:%Y%m%d}", f"{d:%Y%m%d}.txt") for d in days]


def test_scraper_downloads_once_and_records_provenance(tmp_path: Path) -> None:
    client = _FakeClient()
    scraper = _DailyScraper(tmp_path / "fake", client=client)
    paths = scraper.scrape(WINDOW)
    assert [p.name for p in paths] == ["20200101.txt", "20200102.txt"]
    scraper.scrape(WINDOW)
    assert len(client.calls) == 2  # second run skipped current files
    scraper.scrape(WINDOW, force=True)
    assert len(client.calls) == 4


class _CsvReader(DatasetReader):
    schema = TableSchema(columns=(ColumnSpec("bz_nT", min_value=-500, max_value=500),))
    fill_values: ClassVar[dict[str, tuple[float, ...]]] = {"bz_nT": (999.9,)}

    def _parse(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path, parse_dates=["time"]).set_index("time")
        df.index = pd.DatetimeIndex(df.index).tz_localize("UTC")
        return df


def test_reader_cleans_fill_values_and_sorts(tmp_path: Path) -> None:
    f1, f2 = tmp_path / "b.csv", tmp_path / "a.csv"
    f1.write_text("time,bz_nT\n2020-01-02,999.9\n")
    f2.write_text("time,bz_nT\n2020-01-01,-3.5\n")
    df = _CsvReader().read([f1, f2])
    assert df.index.is_monotonic_increasing
    assert df["bz_nT"].isna().tolist() == [False, True]


def test_reader_requires_paths() -> None:
    with pytest.raises(ValueError, match="at least one path"):
        _CsvReader().read([])


class _AddOne(Preprocessor):
    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        return data + 1


class _CenterOnTrain(Preprocessor):
    def __init__(self) -> None:
        self._mean = 0.0

    def fit(self, data: pd.DataFrame) -> "_CenterOnTrain":
        self._mean = float(data["x"].to_numpy().mean())
        self._mark_fitted()
        return self

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        self._require_fitted()
        return data.assign(x=data["x"] - self._mean)


def test_pipeline_fits_in_order_and_requires_fit() -> None:
    pipeline = PreprocessingPipeline([_AddOne(), _CenterOnTrain()])
    with pytest.raises(NotFittedError):
        pipeline.transform(pd.DataFrame({"x": [1.0]}))
    train = pd.DataFrame({"x": [0.0, 2.0]})
    pipeline.fit(train)
    # mean learned on train after +1 is 2.0; applied to new data
    assert pipeline.transform(pd.DataFrame({"x": [5.0]}))["x"].tolist() == [4.0]
