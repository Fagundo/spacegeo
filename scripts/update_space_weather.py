"""Download / refresh the committed space-weather archives in configs/space_weather.yaml.

Usage::

    uv run python scripts/update_space_weather.py
    uv run python scripts/update_space_weather.py --only omni2
    uv run python scripts/update_space_weather.py --as-of 2026-11-23T00:00Z
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from spacegeo.common.log import get_logger
from spacegeo.common.paths import ProjectPaths
from spacegeo.common.time import to_utc
from spacegeo.data.io.base import READERS
from spacegeo.data.io.gfz_kp import GfzKpReader
from spacegeo.data.io.omni import OmniReader
from spacegeo.data.io.yearly_archive import YearlyArchive
from spacegeo.data.scraping.base import SCRAPERS
from spacegeo.data.scraping.gfz_kp import GfzKpScraper
from spacegeo.data.scraping.omni import OmniScraper
from spacegeo.monitoring.archive_update import ArchiveUpdater, UpdatePolicy
from spacegeo.monitoring.config import SpaceWeatherConfig, SpaceWeatherSpec

_log = get_logger("update_space_weather")
_REGISTERED = (OmniScraper, OmniReader, GfzKpScraper, GfzKpReader)
"""Importing these registers them under their source names."""


class SpaceWeatherRefresh:
    """Builds one updater per archive (scraper + reader chosen by name) and runs them."""

    def __init__(self, project: ProjectPaths, config: SpaceWeatherConfig) -> None:
        self._project = project
        self._config = config

    def run(self, as_of: pd.Timestamp, only: str | None = None) -> None:
        """Update every archive (or just ``only``)."""
        for spec in self._config.sources:
            if only is None or spec.name == only:
                _log.info("Updating %s", spec.name)
                self._updater(spec).update(first_year=self._config.first_year, as_of=as_of)

    def _updater(self, spec: SpaceWeatherSpec) -> ArchiveUpdater:
        reader = READERS.get(spec.source)()
        return ArchiveUpdater(
            scraper=SCRAPERS.get(spec.source)(self._project.raw_source(spec.source)),
            reader=reader,
            archive=YearlyArchive(self._project.data_space_weather / spec.name, reader.schema),
            policy=UpdatePolicy(refresh_years=self._config.refresh_years, unique_column=None),
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the committed space-weather archives.")
    parser.add_argument("--config", type=Path, default=Path("configs/space_weather.yaml"))
    parser.add_argument("--only", help="Update just this archive name.")
    parser.add_argument(
        "--as-of", help="Fetch up to this instant (ISO-8601 with offset). Default: now."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    project = ProjectPaths.discover()
    config = SpaceWeatherConfig.from_yaml(project.root / args.config)
    as_of = to_utc(args.as_of) if args.as_of else to_utc(pd.Timestamp.now(tz="UTC"))
    SpaceWeatherRefresh(project, config).run(as_of, only=args.only)
