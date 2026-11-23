"""Download / refresh the committed catalog archives listed in configs/catalogs.yaml.

Missing years are fetched; the last two years are always re-fetched because
ComCat revises recent events.

Usage::

    uv run python scripts/update_catalog.py
    uv run python scripts/update_catalog.py --only comcat_M2.5_cascadia
    uv run python scripts/update_catalog.py --as-of 2026-11-23T00:00Z
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from spacegeo.common.log import get_logger
from spacegeo.common.paths import ProjectPaths
from spacegeo.common.time import to_utc
from spacegeo.data.io.catalog_archive import CatalogArchive
from spacegeo.data.io.comcat import ComCatReader
from spacegeo.data.scraping.comcat import ComCatScraper
from spacegeo.evaluation.anomaly import RegionConfig
from spacegeo.monitoring.catalog_update import CatalogUpdater
from spacegeo.monitoring.config import CatalogsConfig, CatalogSpec

_log = get_logger("update_catalog")


class CatalogRefresh:
    """Builds one updater per archive and runs them."""

    def __init__(self, project: ProjectPaths, config: CatalogsConfig) -> None:
        self._project = project
        self._config = config
        self._regions = {
            r.name: r for r in RegionConfig.load_all(project.root / config.regions_file)
        }

    def run(self, as_of: pd.Timestamp, only: str | None = None) -> None:
        """Update every archive (or just ``only``)."""
        for spec in self._config.catalogs:
            if only is None or spec.name == only:
                _log.info("Updating %s", spec.name)
                self._updater(spec).update(first_year=self._config.first_year, as_of=as_of)

    def _updater(self, spec: CatalogSpec) -> CatalogUpdater:
        bounds = None
        if spec.region is not None:
            bounds = [b.box for b in self._regions[spec.region].boxes]
        scraper = ComCatScraper(
            self._project.raw_source(spec.name),
            min_magnitude=spec.min_magnitude,
            chunk=spec.chunk,
            bounds=bounds,
        )
        archive = CatalogArchive(self._project.data_catalog / spec.name)
        return CatalogUpdater(scraper=scraper, reader=ComCatReader(), archive=archive)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the committed catalog archives.")
    parser.add_argument("--catalogs", type=Path, default=Path("configs/catalogs.yaml"))
    parser.add_argument("--only", help="Update just this archive name.")
    parser.add_argument(
        "--as-of", help="Fetch up to this instant (ISO-8601 with offset). Default: now."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    project = ProjectPaths.discover()
    config = CatalogsConfig.from_yaml(project.root / args.catalogs)
    as_of = to_utc(args.as_of) if args.as_of else to_utc(pd.Timestamp.now(tz="UTC"))
    CatalogRefresh(project, config).run(as_of, only=args.only)
