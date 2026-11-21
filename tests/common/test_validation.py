import numpy as np
import pandas as pd
import pytest

from spacegeo.common.exceptions import SchemaError
from spacegeo.common.validation import ColumnSpec, TableSchema

SCHEMA = TableSchema(
    columns=(
        ColumnSpec("mag", min_value=0, max_value=10, nullable=False),
        ColumnSpec("depth_km", min_value=0, max_value=800),
    )
)


def _frame(**overrides: list[float]) -> pd.DataFrame:
    data = {"mag": [5.0, 6.0], "depth_km": [10.0, np.nan]} | overrides
    return pd.DataFrame(data, index=pd.date_range("2020", periods=2, freq="D", tz="UTC"))


def test_valid_frame_passes() -> None:
    df = _frame()
    assert SCHEMA.validate(df) is df


@pytest.mark.parametrize(
    ("df", "message"),
    [
        (_frame(mag=[5.0, 11.0]), "above 10"),
        (_frame(mag=[5.0, np.nan]), "null"),
        (_frame(depth_km=[-1.0, 1.0]), "below 0"),
        (_frame().assign(extra=1), "undeclared"),
        (_frame().drop(columns="depth_km"), "missing"),
        (_frame().iloc[::-1], "not sorted"),
        (_frame().tz_localize(None), "UTC"),
    ],
)
def test_violations_are_reported(df: pd.DataFrame, message: str) -> None:
    with pytest.raises(SchemaError, match=message):
        SCHEMA.validate(df)
