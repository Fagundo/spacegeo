"""Dataset reader interface.

A reader only knows how to parse its format (:meth:`DatasetReader._parse`).
The base class concatenates files, converts fill values to NaN, sorts, and
validates against the reader's :class:`~spacegeo.common.validation.TableSchema`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import ClassVar

import numpy as np
import pandas as pd

from spacegeo.common.registry import Registry
from spacegeo.common.validation import TableSchema


class DatasetReader(ABC):
    """Reads one dataset format into a validated, UTC-indexed DataFrame.

    Subclasses set :attr:`schema`, optionally :attr:`fill_values`, and
    implement :meth:`_parse`.
    """

    schema: ClassVar[TableSchema]
    fill_values: ClassVar[Mapping[str, tuple[float, ...]]] = {}

    def read(self, paths: Sequence[Path]) -> pd.DataFrame:
        """Parse, clean and validate one or more raw files.

        Raises:
            ValueError: If ``paths`` is empty.
            SchemaError: If the result violates :attr:`schema`.
        """
        if not paths:
            raise ValueError(f"{type(self).__name__}.read needs at least one path.")
        df = pd.concat([self._parse(path) for path in paths])
        df = self._replace_fill_values(df).sort_index()
        return self.schema.validate(df)

    @abstractmethod
    def _parse(self, path: Path) -> pd.DataFrame:
        """Parse one raw file. Must return a UTC-indexed frame."""

    def _replace_fill_values(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for column, sentinels in self.fill_values.items():
            if column in out.columns:
                out[column] = out[column].replace(list(sentinels), np.nan)
        return out


READERS: Registry[DatasetReader] = Registry("reader")
