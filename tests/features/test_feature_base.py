from collections.abc import Sequence
from typing import Self

import numpy as np
import pandas as pd
import pytest

from spacegeo.common.time import duration
from spacegeo.features.base import Feature, FeatureSet


class _Count(Feature):
    input_columns = ("value",)

    @property
    def output_names(self) -> tuple[str, ...]:
        return (f"value_count_{int(self.lookback / duration(hours=1))}h",)

    @classmethod
    def example(cls) -> Self:
        return cls(lookback=duration(hours=3))

    def _compute_window(self, window: pd.DataFrame, forecast_time: pd.Timestamp) -> Sequence[float]:
        return [float(len(window))]


INDEX = pd.date_range("2020-01-01", periods=10, freq="h", tz="UTC")
DATA = pd.DataFrame({"value": np.arange(10.0)}, index=INDEX)


def test_window_excludes_forecast_time() -> None:
    out = _Count.example().compute(DATA, pd.DatetimeIndex([INDEX[5]]))
    # rows at hours 2, 3, 4 are in [t-3h, t); the row at t itself is excluded
    assert out.iloc[0, 0] == 3.0


def test_min_observations_yields_nan() -> None:
    feature = _Count(lookback=duration(hours=3), min_observations=2)
    out = feature.compute(DATA, pd.DatetimeIndex([INDEX[1]]))
    assert np.isnan(out.iloc[0, 0])


def test_rejects_unsorted_data() -> None:
    with pytest.raises(ValueError, match="sorted"):
        _Count.example().compute(DATA.iloc[::-1], pd.DatetimeIndex([INDEX[5]]))


def test_feature_set_joins_and_rejects_duplicates() -> None:
    fs = FeatureSet([_Count.example(), _Count(lookback=duration(hours=6))])
    out = fs.compute(DATA, pd.DatetimeIndex(INDEX[6:]))
    assert list(out.columns) == ["value_count_3h", "value_count_6h"]
    assert fs.max_lookback == duration(hours=6)
    with pytest.raises(ValueError, match="Duplicate"):
        FeatureSet([_Count.example(), _Count.example()])
