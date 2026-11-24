"""Committed, per-year store of the parsed ComCat earthquake catalog."""

from __future__ import annotations

from pathlib import Path

from spacegeo.common.validation import TableSchema
from spacegeo.data.io.comcat import ComCatReader
from spacegeo.data.io.yearly_archive import YearlyArchive


class CatalogArchive(YearlyArchive):
    """A :class:`YearlyArchive` of ComCat events (``data/catalog/<name>``).

    Args:
        root: Archive directory (e.g. ``data/catalog/comcat_M4.5``).
        schema: Schema every stored frame must satisfy.
    """

    def __init__(self, root: Path, schema: TableSchema = ComCatReader.schema) -> None:
        super().__init__(root, schema)
