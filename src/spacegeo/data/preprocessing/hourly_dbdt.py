"""Reduce 1-minute magnetometer data to hourly horizontal dB/dt statistics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from spacegeo.common.time import duration
from spacegeo.common.validation import ColumnSpec, TableSchema
from spacegeo.data.preprocessing.base import PREPROCESSORS, Preprocessor


@PREPROCESSORS.register("hourly_dbdt")
class HourlyHorizontalDbDt(Preprocessor):
    """Hourly max and mean of |dB_H/dt| from consecutive 1-minute samples.

    dB_H/dt for minutes s and s + 1 min is sqrt(dX^2 + dY^2) per minute
    (nT/min). Only pairs whose two samples both start inside the same hour
    count toward that hour (at most 59 pairs), so every hourly row uses data
    that ended by the end of its hour. Rows are stamped at the hour start.

    Output columns:

    - ``dbh_dt_max_nT_min``: largest |dB_H/dt| in the hour (nT/min)
    - ``dbh_dt_mean_nT_min``: mean |dB_H/dt| in the hour (nT/min)
    - ``n_pairs``: valid minute pairs behind the statistics

    Hours with fewer than ``min_pairs`` valid pairs get NaN statistics
    (the row is kept, with its ``n_pairs``).

    Args:
        min_pairs: Minimum valid minute pairs for an hour to be defined.
    """

    MINUTE = duration(minutes=1)
    HOUR = duration(hours=1)
    OUTPUT_SCHEMA = TableSchema(
        columns=(
            ColumnSpec("dbh_dt_max_nT_min", min_value=0, max_value=1e5),
            ColumnSpec("dbh_dt_mean_nT_min", min_value=0, max_value=1e5),
            ColumnSpec("n_pairs", min_value=0, max_value=59, nullable=False),
        )
    )
    """Schema of the hourly output (what the committed archive stores)."""

    def __init__(self, min_pairs: int = 30) -> None:
        if not 1 <= min_pairs <= 59:  # noqa: PLR2004
            raise ValueError("min_pairs must be in [1, 59].")
        self._min_pairs = min_pairs

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Minute frame with ``x_nT``, ``y_nT`` (UTC index) -> hourly frame."""
        index = pd.DatetimeIndex(data.index)
        x = data["x_nT"].to_numpy(dtype=np.float64)
        y = data["y_nT"].to_numpy(dtype=np.float64)
        ns = np.asarray(index.as_unit("ns").asi8)
        step = np.diff(ns)
        hours = pd.DatetimeIndex(pd.to_datetime(ns - ns % self.HOUR.value, utc=True))
        same_hour = np.asarray(hours[1:] == hours[:-1])
        valid = (step == self.MINUTE.value) & same_hour
        rate = np.hypot(np.diff(x), np.diff(y))
        valid &= np.isfinite(rate)
        pairs = pd.DataFrame({"rate": rate[valid]}, index=hours[:-1][valid])
        grouped = pairs.groupby(level=0)["rate"]
        out = pd.DataFrame(
            {
                "dbh_dt_max_nT_min": grouped.max(),
                "dbh_dt_mean_nT_min": grouped.mean(),
                "n_pairs": grouped.size().astype(np.float64),
            }
        )
        grid = pd.date_range(hours.min(), hours.max(), freq="h") if len(index) else hours[:0]
        out = out.reindex(grid)
        out["n_pairs"] = out["n_pairs"].fillna(0.0)
        thin = out["n_pairs"].to_numpy() < self._min_pairs
        out.loc[thin, ["dbh_dt_max_nT_min", "dbh_dt_mean_nT_min"]] = np.nan
        out.index.name = "time"
        return out
