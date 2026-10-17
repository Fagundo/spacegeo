"""Declarative DataFrame schemas, shared by every reader and preprocessor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
from pandas.api import types as ptypes

from spacegeo.common.exceptions import SchemaError, TimeZoneError
from spacegeo.common.time import require_utc_index

ColumnKind = Literal["float", "int", "str", "bool"]

_KIND_CHECKS = {
    "float": ptypes.is_numeric_dtype,
    "int": ptypes.is_integer_dtype,
    "str": lambda s: ptypes.is_string_dtype(s) or ptypes.is_object_dtype(s),
    "bool": ptypes.is_bool_dtype,
}


@dataclass(frozen=True)
class ColumnSpec:
    """Expected properties of one column.

    Attributes:
        name: Column name, carrying its unit (e.g. ``bz_nT``).
        kind: Expected dtype family.
        min_value: Inclusive lower bound, if any.
        max_value: Inclusive upper bound, if any.
        nullable: Whether NaN/None is allowed.
    """

    name: str
    kind: ColumnKind = "float"
    min_value: float | None = None
    max_value: float | None = None
    nullable: bool = True

    def errors(self, series: pd.Series) -> list[str]:
        """Return human-readable violations for ``series`` (empty if valid)."""
        problems: list[str] = []
        if not _KIND_CHECKS[self.kind](series):
            return [f"{self.name}: expected {self.kind}, got {series.dtype}"]
        if not self.nullable and series.isna().any():
            problems.append(f"{self.name}: {int(series.isna().sum())} null values")
        values = series.dropna()
        if self.min_value is not None and (values < self.min_value).any():
            problems.append(f"{self.name}: values below {self.min_value}")
        if self.max_value is not None and (values > self.max_value).any():
            problems.append(f"{self.name}: values above {self.max_value}")
        return problems


@dataclass(frozen=True)
class TableSchema:
    """Expected structure of a time-indexed DataFrame.

    Attributes:
        columns: Column specifications.
        require_utc_index: Index must be a UTC ``DatetimeIndex``.
        require_sorted_index: Index must be monotonically increasing.
        allow_extra_columns: Whether undeclared columns are tolerated.
    """

    columns: tuple[ColumnSpec, ...]
    require_utc_index: bool = True
    require_sorted_index: bool = True
    allow_extra_columns: bool = False

    @property
    def column_names(self) -> tuple[str, ...]:
        """Declared column names, in order."""
        return tuple(spec.name for spec in self.columns)

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return ``df`` unchanged if valid.

        Raises:
            SchemaError: Listing every violation found.
        """
        problems = self._index_errors(df) + self._column_errors(df)
        if problems:
            raise SchemaError("Schema validation failed:\n  " + "\n  ".join(problems))
        return df

    def _index_errors(self, df: pd.DataFrame) -> list[str]:
        problems: list[str] = []
        if self.require_utc_index:
            try:
                require_utc_index(df.index)
            except TimeZoneError as exc:
                problems.append(f"index: {exc}")
        if self.require_sorted_index and not df.index.is_monotonic_increasing:
            problems.append("index: not sorted ascending")
        return problems

    def _column_errors(self, df: pd.DataFrame) -> list[str]:
        problems: list[str] = []
        missing = [name for name in self.column_names if name not in df.columns]
        problems += [f"{name}: missing column" for name in missing]
        if not self.allow_extra_columns:
            extra = sorted(set(df.columns) - set(self.column_names))
            problems += [f"{name}: undeclared column" for name in extra]
        for spec in self.columns:
            if spec.name not in df.columns:
                continue
            column = df[spec.name]
            if isinstance(column, pd.Series):
                problems += spec.errors(column)
            else:
                problems.append(f"{spec.name}: duplicated column")
        return problems
