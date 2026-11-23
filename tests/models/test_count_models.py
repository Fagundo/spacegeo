import math

import numpy as np
import pandas as pd
import pytest

from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.models.base import ModelData
from spacegeo.models.count import NegativeBinomialCountModel, PoissonCountModel

WINDOW = TimeWindow(to_utc("2000-01-01T00:00Z"), to_utc("2000-03-11T00:00Z"))  # 10 weeks


def _weekly(counts: list[int]) -> ModelData:
    times = [
        WINDOW.start + duration(days=7 * w + 1) for w, c in enumerate(counts) for _ in range(c)
    ]
    return ModelData(
        events=pd.DataFrame({"mag": 5.0}, index=pd.DatetimeIndex(times)), window=WINDOW
    )


def test_poisson_tail_matches_closed_form() -> None:
    model = PoissonCountModel(duration(days=7)).fit(_weekly([2] * 10))
    assert model.expected_count() == pytest.approx(2.0)
    expected = 1 - sum(math.exp(-2) * 2**k / math.factorial(k) for k in range(5))
    assert model.survival(5) == pytest.approx(expected, rel=1e-12)


def test_negative_binomial_captures_overdispersion() -> None:
    data = _weekly([0, 0, 0, 1, 0, 0, 15, 0, 1, 3])
    nb = NegativeBinomialCountModel(duration(days=7)).fit(data)
    po = PoissonCountModel(duration(days=7)).fit(data)
    assert nb.expected_count() == pytest.approx(2.0)
    assert np.isfinite(nb.dispersion)
    assert nb.survival(10) > 100 * po.survival(10)


def test_negative_binomial_falls_back_to_poisson() -> None:
    data = _weekly([2] * 10)
    nb = NegativeBinomialCountModel(duration(days=7)).fit(data)
    assert math.isinf(nb.dispersion)
    assert nb.survival(5) == pytest.approx(
        PoissonCountModel(duration(days=7)).fit(data).survival(5)
    )


def test_window_counts_drop_partial_bin() -> None:
    model = PoissonCountModel(duration(days=7))
    counts = model.window_counts(_weekly([1, 2, 3, 0, 0, 0, 0, 0, 0, 4]))
    assert counts.tolist() == [1, 2, 3, 0, 0, 0, 0, 0, 0, 4]
    short = ModelData(
        events=_weekly([1]).events, window=TimeWindow(WINDOW.start, WINDOW.start + duration(days=3))
    )
    with pytest.raises(ValueError, match="shorter"):
        model.window_counts(short)


def test_horizon_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        PoissonCountModel(duration(days=0))
