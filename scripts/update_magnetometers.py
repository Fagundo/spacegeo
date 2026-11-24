"""Download / refresh hourly horizontal dB/dt archives for INTERMAGNET observatories.

For each station: fetch the HAPI info (coordinates, availability), write
``station.json`` next to the archive, then download missing years (and
always the most recent ones), reduce 1-minute X/Y to hourly |dB_H/dt| and
store one ``<year>.csv.gz`` per year. Raw minute files are deleted after
each year is stored, so a CI runner never holds more than one year.

Usage::

    uv run python scripts/update_magnetometers.py               # every station
    uv run python scripts/update_magnetometers.py --station CMO
    uv run python scripts/update_magnetometers.py --list-json   # for CI matrices
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from spacegeo.common.log import get_logger
from spacegeo.common.paths import ProjectPaths
from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.data.io.intermagnet import IntermagnetReader, IntermagnetStation
from spacegeo.data.io.yearly_archive import YearlyArchive
from spacegeo.data.preprocessing.hourly_dbdt import HourlyHorizontalDbDt
from spacegeo.data.scraping.intermagnet import IntermagnetInfoScraper, IntermagnetScraper
from spacegeo.monitoring.archive_update import ArchiveUpdater, UpdatePolicy
from spacegeo.monitoring.config import MagnetometerConfig

_log = get_logger("update_magnetometers")


class MagnetometerRefresh:
    """Updates one station's info and hourly archive."""

    def __init__(self, project: ProjectPaths, config: MagnetometerConfig) -> None:
        self._project = project
        self._config = config

    def run(self, station: str, as_of: pd.Timestamp) -> list[int]:
        """Refresh ``station``; returns the years whose file changed."""
        code = station.upper()
        raw = self._project.raw_source("intermagnet") / code
        info_path = IntermagnetInfoScraper(raw, code).scrape(_whole_span(), force=True)[0]
        meta = IntermagnetStation.from_info(code, info_path)
        root = self._project.data_space_weather / "intermagnet" / code
        root.mkdir(parents=True, exist_ok=True)
        (root / "station.json").write_text(json.dumps(meta.to_dict(), indent=2) + "\n")
        updater = ArchiveUpdater(
            IntermagnetScraper(raw, code),
            IntermagnetReader(),
            YearlyArchive(root, HourlyHorizontalDbDt.OUTPUT_SCHEMA),
            UpdatePolicy(
                refresh_years=self._config.refresh_years,
                unique_column=None,
                transform=HourlyHorizontalDbDt(self._config.min_pairs),
                discard_raw=True,
            ),
        )
        stop = min(as_of, meta.stop + duration(minutes=1))
        first = max(self._config.first_year, meta.start.year)
        _log.info("%s (%s): %d to %s", code, meta.name, first, stop)
        return updater.update(first_year=first, as_of=stop)


def _whole_span() -> TimeWindow:
    """Any window: the info scraper ignores it."""
    return TimeWindow(to_utc("1900-01-01T00:00Z"), to_utc("2100-01-01T00:00Z"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh INTERMAGNET hourly dB/dt archives.")
    parser.add_argument("--config", type=Path, default=Path("configs/magnetometers.yaml"))
    parser.add_argument("--station", help="Update just this IAGA code.")
    parser.add_argument("--list-json", action="store_true", help="Print the station list as JSON.")
    parser.add_argument("--as-of", help="Fetch up to this instant (ISO-8601). Default: now.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    project = ProjectPaths.discover()
    config = MagnetometerConfig.from_yaml(project.root / args.config)
    if args.list_json:
        print(json.dumps(list(config.stations)))  # noqa: T201 - consumed by the CI matrix
    else:
        as_of = to_utc(args.as_of) if args.as_of else to_utc(pd.Timestamp.now(tz="UTC"))
        refresh = MagnetometerRefresh(project, config)
        for code in [args.station] if args.station else config.stations:
            refresh.run(code, as_of)
