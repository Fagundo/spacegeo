"""Reader for NASA OMNI2 hourly ASCII files (``omni2_YYYY.dat``).

Format reference: https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2.text
Each row is one hour and 55 whitespace-separated "words". We keep the words
needed for coupling, variability and index features; the rest are dropped.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import numpy as np
import numpy.typing as npt
import pandas as pd

from spacegeo.common.exceptions import SchemaError
from spacegeo.common.validation import ColumnSpec, TableSchema
from spacegeo.data.io.base import READERS, DatasetReader


@READERS.register("omni2")
class OmniReader(DatasetReader):
    """Parses OMNI2 hourly rows into a UTC, hour-start indexed frame.

    Output columns (GSM unless noted; hourly averages):

    - ``b_mag_nT``: mean field magnitude |B| (nT)
    - ``bx_gse_nT``, ``by_gsm_nT``, ``bz_gsm_nT``: IMF components (nT)
    - ``sigma_bz_nT``: standard deviation of Bz (GSE) within the hour (nT)
    - ``temperature_K``: proton temperature (K)
    - ``density_cm3``: proton density (cm^-3)
    - ``speed_km_s``: bulk flow speed (km/s)
    - ``pdyn_nPa``: flow pressure (nPa)
    - ``ey_mV_m``: dawn-dusk electric field -V*Bz (mV/m)
    - ``kp``: planetary Kp, converted from OMNI's 10*Kp code to thirds (0-9)
    - ``sunspot_number``: daily sunspot number R (version 2)
    - ``dst_nT``: Dst index (nT)
    - ``ae_nT``, ``al_nT``, ``au_nT``: auroral electrojet indices (nT)
    - ``ap``: 3-hourly ap index (units of 2 nT)
    - ``f107_sfu``: daily 10.7 cm solar flux (solar flux units)
    """

    N_WORDS = 55
    WORDS: ClassVar[dict[int, str]] = {
        9: "b_mag_nT",
        13: "bx_gse_nT",
        16: "by_gsm_nT",
        17: "bz_gsm_nT",
        22: "sigma_bz_nT",
        23: "temperature_K",
        24: "density_cm3",
        25: "speed_km_s",
        29: "pdyn_nPa",
        36: "ey_mV_m",
        39: "kp",
        40: "sunspot_number",
        41: "dst_nT",
        42: "ae_nT",
        50: "ap",
        51: "f107_sfu",
        53: "al_nT",
        54: "au_nT",
    }
    """1-based OMNI2 word number -> output column."""

    KP_FILL = 99
    """OMNI's fill for the 10*Kp code; masked before converting to thirds."""

    fill_values: ClassVar[dict[str, tuple[float, ...]]] = {
        "b_mag_nT": (999.9,),
        "bx_gse_nT": (999.9,),
        "by_gsm_nT": (999.9,),
        "bz_gsm_nT": (999.9,),
        "sigma_bz_nT": (999.9,),
        "temperature_K": (9999999.0,),
        "density_cm3": (999.9,),
        "speed_km_s": (9999.0,),
        "pdyn_nPa": (99.99,),
        "ey_mV_m": (999.99,),
        "sunspot_number": (999.0,),
        "dst_nT": (99999.0,),
        "ae_nT": (9999.0,),
        "ap": (999.0,),
        "f107_sfu": (999.9,),
        "al_nT": (99999.0,),
        "au_nT": (99999.0,),
    }

    schema = TableSchema(
        columns=(
            ColumnSpec("b_mag_nT", min_value=0, max_value=200),
            ColumnSpec("bx_gse_nT", min_value=-200, max_value=200),
            ColumnSpec("by_gsm_nT", min_value=-200, max_value=200),
            ColumnSpec("bz_gsm_nT", min_value=-200, max_value=200),
            ColumnSpec("sigma_bz_nT", min_value=0, max_value=200),
            ColumnSpec("temperature_K", min_value=0, max_value=1e8),
            ColumnSpec("density_cm3", min_value=0, max_value=300),
            ColumnSpec("speed_km_s", min_value=100, max_value=3000),
            ColumnSpec("pdyn_nPa", min_value=0, max_value=99),
            ColumnSpec("ey_mV_m", min_value=-200, max_value=200),
            ColumnSpec("kp", min_value=0, max_value=9),
            ColumnSpec("sunspot_number", min_value=0, max_value=600),
            ColumnSpec("dst_nT", min_value=-2000, max_value=300),
            ColumnSpec("ae_nT", min_value=0, max_value=5000),
            ColumnSpec("ap", min_value=0, max_value=400),
            ColumnSpec("f107_sfu", min_value=0, max_value=1000),
            ColumnSpec("al_nT", min_value=-5000, max_value=500),
            ColumnSpec("au_nT", min_value=-500, max_value=5000),
        )
    )

    def _parse(self, path: Path) -> pd.DataFrame:
        raw = pd.read_csv(path, sep=r"\s+", header=None, dtype=float)
        if raw.shape[1] != self.N_WORDS:
            raise SchemaError(
                f"{path.name}: expected {self.N_WORDS} OMNI2 words per row, got {raw.shape[1]}."
            )
        words = raw.to_numpy()
        out = pd.DataFrame({name: words[:, word - 1] for word, name in self.WORDS.items()})
        out["kp"] = self._kp_thirds(words[:, 38])
        out.index = self._hour_index(words)
        out.index.name = "time"
        return out

    def _kp_thirds(self, code: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """OMNI stores 10*Kp (3- = 27, 3o = 30, 3+ = 33); return Kp in exact thirds."""
        masked = np.where(code == self.KP_FILL, np.nan, code)
        return np.round(masked * 0.3) / 3.0

    @staticmethod
    def _hour_index(words: npt.NDArray[np.float64]) -> pd.DatetimeIndex:
        year_doy = [
            f"{int(y):04d}{int(d):03d}" for y, d in zip(words[:, 0], words[:, 1], strict=True)
        ]
        days = pd.DatetimeIndex(pd.to_datetime(year_doy, format="%Y%j", utc=True))
        return days + pd.to_timedelta(words[:, 2].astype(int), unit="h")
