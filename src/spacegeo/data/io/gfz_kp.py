"""Reader for the GFZ ``Kp_ap_Ap_SN_F107_since_1932.txt`` index file.

Format reference: https://kp.gfz.de/en/data (file header). One row per day:
``YYYY MM DD days days_m Bsr dB Kp1..Kp8 ap1..ap8 Ap SN F10.7obs F10.7adj D``.
Missing values are -1; ``D`` is 0 (Kp and SN preliminary), 1 (Kp
definitive) or 2 (both definitive).
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import numpy as np
import pandas as pd

from spacegeo.common.exceptions import SchemaError
from spacegeo.common.validation import ColumnSpec, TableSchema
from spacegeo.data.io.base import READERS, DatasetReader


@READERS.register("gfz_kp")
class GfzKpReader(DatasetReader):
    """Parses the GFZ daily rows into a 3-hourly Kp/ap series.

    Each output row covers the 3-hour interval starting at its index
    timestamp (00, 03, ..., 21 UTC).

    Output columns:

    - ``kp``: planetary Kp in thirds (0-9, dimensionless)
    - ``ap``: 3-hourly equivalent amplitude (units of 2 nT)
    - ``kp_definitive``: whether GFZ marks the day's Kp as definitive

    Daily SN and F10.7 are not kept here; OMNI2 carries them hourly.
    """

    N_COLUMNS = 28
    SLOTS = 8
    KP_COLUMNS = slice(7, 15)
    AP_COLUMNS = slice(15, 23)
    DEFINITIVE_COLUMN = 27

    fill_values: ClassVar[dict[str, tuple[float, ...]]] = {"kp": (-1.0,), "ap": (-1.0,)}

    schema = TableSchema(
        columns=(
            ColumnSpec("kp", min_value=0, max_value=9),
            ColumnSpec("ap", min_value=0, max_value=400),
            ColumnSpec("kp_definitive", kind="bool", nullable=False),
        )
    )

    def _parse(self, path: Path) -> pd.DataFrame:
        raw = pd.read_csv(path, sep=r"\s+", header=None, comment="#", dtype=float)
        if raw.shape[1] != self.N_COLUMNS:
            raise SchemaError(
                f"{path.name}: expected {self.N_COLUMNS} GFZ columns per row, got {raw.shape[1]}."
            )
        out = pd.DataFrame(
            {
                "kp": raw.iloc[:, self.KP_COLUMNS].to_numpy().ravel(),
                "ap": raw.iloc[:, self.AP_COLUMNS].to_numpy().ravel(),
                "kp_definitive": np.repeat(raw[self.DEFINITIVE_COLUMN].to_numpy() >= 1, self.SLOTS),
            },
            index=self._slot_index(raw),
        )
        out.index.name = "time"
        return out

    def _slot_index(self, raw: pd.DataFrame) -> pd.DatetimeIndex:
        days = pd.DatetimeIndex(
            pd.to_datetime(
                pd.DataFrame({"year": raw[0], "month": raw[1], "day": raw[2]}).astype(int),
                utc=True,
            )
        )
        offsets = pd.to_timedelta(np.tile(np.arange(self.SLOTS) * 3, len(raw)), unit="h")
        return days.repeat(self.SLOTS) + offsets
