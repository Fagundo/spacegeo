"""Weekly regional seismicity anomaly scan (default: the Ring of Fire).

Reads the committed catalog archive (run ``scripts/update_catalog.py`` first)
and writes to ``results/anomaly/``:

* ``validate``: fit on train (2000-2019), score every validation week
  (2020-2025): calibration (tail rates, PIT), log-score model comparison
  with block-bootstrap intervals, and injection detection power. Re-run
  automatically when the config differs from the one stored with the
  last validation (``results/anomaly/validation/config.yaml``); otherwise
  skipped unless ``--force``.
* ``predict``: refit on train + validation, score every complete test week
  (2026 onward) up to ``--as-of`` and write ``test/latest.md``.

Usage::

    uv run python scripts/scan_anomalies.py validate
    uv run python scripts/scan_anomalies.py predict
    uv run python scripts/scan_anomalies.py predict --as-of 2026-11-23T00:00Z
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import pandas as pd

from spacegeo.common.log import get_logger
from spacegeo.common.paths import ProjectPaths
from spacegeo.common.time import to_utc
from spacegeo.data.io.catalog_archive import CatalogArchive
from spacegeo.monitoring.config import WeeklyScanConfig
from spacegeo.monitoring.report import ScanReportWriter
from spacegeo.monitoring.validation import ValidationSuite
from spacegeo.monitoring.weekly_scan import WeeklyAnomalyScan

_log = get_logger("scan_anomalies")


class ScanCommand:
    """Wires the archive, scan, calibration and report writer together."""

    def __init__(self, project: ProjectPaths, config: WeeklyScanConfig) -> None:
        self._config = config
        catalog = CatalogArchive(
            project.catalog_archive("comcat", config.catalog_min_magnitude)
        ).read()
        self._scan = WeeklyAnomalyScan(config, catalog)
        self._writer = ScanReportWriter(project.results / "anomaly")

    def validate(self, *, force: bool) -> None:
        """Run and store the validation span (again if the config changed)."""
        stored = self._writer.validation_dir / "config.yaml"
        if stored.exists() and not force and self._same_config(stored):
            _log.info("Validation already stored for this config; use --force to redo it.")
            return
        report = ValidationSuite(self._config, self._scan).run()
        self._writer.write_validation(report)
        self._config.to_yaml(stored)
        _log.info("Validation summary:\n%s", report.by_test.round(4).to_string())
        _log.info("Model comparison:\n%s", report.model_comparison.round(4).to_string())

    def predict(self, as_of: pd.Timestamp) -> None:
        """Score the test span up to ``as_of``."""
        results = self._scan.predict(as_of).results
        results.insert(
            results.columns.get_loc("region") + 1, "mc", results["region"].map(self._scan.mc)
        )
        by_test_path = self._writer.validation_dir / "by_test.csv"
        calibration = pd.read_csv(by_test_path, index_col="test") if by_test_path.exists() else None
        self._writer.write_predictions(results, calibration)
        _log.info("Wrote %s", self._writer.test_dir / "latest.md")

    def _same_config(self, stored: Path) -> bool:
        with tempfile.TemporaryDirectory() as tmp:
            current = Path(tmp) / "config.yaml"
            self._config.to_yaml(current)
            return current.read_bytes() == stored.read_bytes()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Weekly regional anomaly scan.")
    parser.add_argument("mode", choices=["validate", "predict"])
    parser.add_argument("--config", type=Path, default=Path("configs/ring_of_fire_scan.yaml"))
    parser.add_argument(
        "--as-of", help="Score weeks ending at or before this instant. Default: now."
    )
    parser.add_argument("--force", action="store_true", help="Redo validation even if stored.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    project = ProjectPaths.discover()
    command = ScanCommand(project, WeeklyScanConfig.from_yaml(project.root / args.config))
    if args.mode == "validate":
        command.validate(force=args.force)
    else:
        command.predict(to_utc(args.as_of) if args.as_of else to_utc(pd.Timestamp.now(tz="UTC")))
