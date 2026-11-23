"""Weekly regional seismicity anomaly scan (default: the Ring of Fire).

Downloads the USGS ComCat baseline and the most recent window, then runs two
tests per region and writes them to ``runs/<UTC>_anomaly-scan/``:

* ``activity``   - raw catalog vs. a negative binomial fitted to past
  weekly counts. Aftershock sequences raise the variance, so only activity
  unusual *even allowing for typical clustering* is flagged.
* ``mainshocks`` - Gardner-Knopoff declustered catalog vs. a Poisson rate.
  Flags more independent mainshocks than usual (not one big sequence).

Usage::

    uv run python scripts/scan_anomalies.py                    # week ending today 00:00 UTC
    uv run python scripts/scan_anomalies.py --end 2026-11-23T00:00Z
    uv run python scripts/scan_anomalies.py --config configs/ring_of_fire_scan.yaml
"""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from spacegeo.common.log import get_logger
from spacegeo.common.paths import ProjectPaths
from spacegeo.common.time import TimeWindow, duration, to_utc
from spacegeo.data.io.comcat import ComCatReader
from spacegeo.data.preprocessing.gardner_knopoff import GardnerKnopoffDeclusterer
from spacegeo.data.preprocessing.magnitude_cut import MagnitudeCut
from spacegeo.data.scraping.comcat import ComCatScraper
from spacegeo.evaluation.anomaly import AnomalyScanConfig, RegionalAnomalyScanner
from spacegeo.models.base import CountModel
from spacegeo.models.count import NegativeBinomialCountModel, PoissonCountModel

_log = get_logger("scan_anomalies")


@dataclass(frozen=True)
class AnomalyScanRun:
    """One end-to-end scan: fetch, clean, test, write."""

    config: AnomalyScanConfig
    observation: TimeWindow
    paths: ProjectPaths

    def run(self) -> Path:
        """Execute the scan and return the run directory."""
        catalog = self._load_catalog()
        horizon = duration(days=self.config.horizon_days)
        declustered = GardnerKnopoffDeclusterer().transform(catalog)
        results = {
            "activity": self._scan(catalog, lambda: NegativeBinomialCountModel(horizon)),
            "mainshocks": self._scan(declustered, lambda: PoissonCountModel(horizon)),
        }
        return self._write(results, n_raw=len(catalog), n_main=len(declustered))

    def _load_catalog(self) -> pd.DataFrame:
        scraper = ComCatScraper(self.paths.raw_source("comcat"), min_magnitude=self.config.mc)
        files = scraper.scrape(self.config.baseline) + scraper.scrape(self.observation)
        catalog = ComCatReader().read(files)
        catalog = catalog.loc[~catalog["event_id"].duplicated(keep="last")]
        return MagnitudeCut(self.config.mc).transform(catalog)

    def _scan(self, events: pd.DataFrame, factory: Callable[[], CountModel]) -> pd.DataFrame:
        scanner = RegionalAnomalyScanner(self.config.regions, factory, fdr=self.config.fdr)
        return scanner.scan(events, self.config.baseline, self.observation)

    def _write(self, results: dict[str, pd.DataFrame], n_raw: int, n_main: int) -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        out = self.paths.runs / f"{stamp}_anomaly-scan"
        out.mkdir(parents=True)
        self.config.to_yaml(out / "config.yaml")
        lines = [
            f"Observation: {self.observation.start} -> {self.observation.end}",
            f"Baseline: {self.config.baseline.start} -> {self.config.baseline.end}",
            f"Commit: {_git_commit()}",
            f"Events M>={self.config.mc}: {n_raw} raw, {n_main} after declustering",
        ]
        for name, table in results.items():
            table.to_csv(out / f"{name}.csv", float_format="%.6g")
            lines += ["", f"## {name}", table.round(4).to_string()]
        (out / "NOTES.md").write_text("\n".join(lines) + "\n")
        _log.info("Wrote %s\n%s", out, "\n".join(lines))
        return out


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() or "unknown"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=Path("configs/ring_of_fire_scan.yaml"))
    parser.add_argument("--end", help="Exclusive end of the window, ISO-8601 with offset.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    project = ProjectPaths.discover()
    cfg = AnomalyScanConfig.from_yaml(project.root / args.config)
    end = to_utc(args.end) if args.end else to_utc(pd.Timestamp.now(tz="UTC").floor("D"))
    AnomalyScanRun(cfg, cfg.observation(end), project).run()
