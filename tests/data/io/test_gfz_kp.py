from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from spacegeo.common.exceptions import SchemaError
from spacegeo.common.time import to_utc
from spacegeo.data.io.gfz_kp import GfzKpReader

FIXTURE = Path(__file__).parents[2] / "fixtures" / "gfz_kp" / "Kp_ap_Ap_SN_F107_sample.txt"


def test_expands_days_to_three_hour_slots() -> None:
    df = GfzKpReader().read([FIXTURE])
    index = pd.DatetimeIndex(df.index)
    assert str(index.tz) == "UTC"
    assert len(df) == 3 * 8
    assert index[0] == to_utc("2015-03-16T00:00Z")
    assert index[9] == to_utc("2015-03-17T03:00Z")
    assert df["kp"].iloc[9] == pytest.approx(5.333)
    assert df["ap"].iloc[12] == pytest.approx(207.0)


def test_missing_values_and_definitive_flag() -> None:
    df = GfzKpReader().read([FIXTURE])
    nowcast = df.loc[df.index >= to_utc("2026-11-22T15:00Z")]
    assert len(nowcast) == 3
    assert np.isnan(nowcast["kp"]).all()
    assert np.isnan(nowcast["ap"]).all()
    assert not df["kp_definitive"].iloc[-1]
    assert df["kp_definitive"].iloc[0]


def test_wrong_column_count_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "kp.txt"
    bad.write_text("2015 03 16 30025 30025.5 2477 13 1.333\n")
    with pytest.raises(SchemaError, match="28 GFZ columns"):
        GfzKpReader().read([bad])
