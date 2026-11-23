"""Download / refresh the committed USGS ComCat archive (data/catalog/).

Missing years are fetched; the last two years are always re-fetched because
ComCat revises recent events.

Usage::

    uv run python scripts/update_catalog.py
    uv run python scripts/update_catalog.py --as-of 2026-11-23T00:00Z
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from spacegeo.common.paths import ProjectPaths
from spacegeo.common.time import to_utc
from spacegeo.data.io.catalog_archive import CatalogArchive
from spacegeo.data.io.comcat import ComCatReader
from spacegeo.data.scraping.comcat import ComCatScraper
from spacegeo.monitoring.catalog_update import CatalogUpdater
from spacegeo.monitoring.config import WeeklyScanConfig


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the committed ComCat archive.")
    parser.add_argument("--config", type=Path, default=Path("configs/ring_of_fire_scan.yaml"))
    parser.add_argument(
        "--as-of", help="Fetch up to this instant (ISO-8601 with offset). Default: now."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    project = ProjectPaths.discover()
    cfg = WeeklyScanConfig.from_yaml(project.root / args.config)
    as_of = to_utc(args.as_of) if args.as_of else to_utc(pd.Timestamp.now(tz="UTC"))
    updater = CatalogUpdater(
        scraper=ComCatScraper(project.raw_source("comcat"), min_magnitude=cfg.mc),
        reader=ComCatReader(),
        archive=CatalogArchive(project.catalog_archive("comcat", cfg.mc)),
    )
    updater.update(first_year=to_utc(cfg.train_start).year, as_of=as_of)
