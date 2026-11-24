"""``spacegeo`` command line: ``spacegeo run <config.yaml>``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from spacegeo.common.log import get_logger
from spacegeo.common.paths import ProjectPaths
from spacegeo.common.run import GitState, RunDirectory
from spacegeo.data.io.catalog_archive import CatalogArchive
from spacegeo.evaluation.anomaly import RegionConfig
from spacegeo.training.anomaly_followup import (
    AnomalyFollowupConfig,
    AnomalyFollowupExperiment,
    AnomalyFollowupReport,
)
from spacegeo.training.etas_baseline import (
    EtasBaselineExperiment,
    EtasExperimentConfig,
    ValidationExperimentConfig,
)
from spacegeo.training.etas_report import EtasBaselineReport
from spacegeo.training.event_forecast import EventForecastConfig, EventForecastExperiment
from spacegeo.training.event_forecast_report import EventForecastReport
from spacegeo.training.small_trigger import (
    SmallTriggerConfig,
    SmallTriggerExperiment,
    SmallTriggerReport,
)

_log = get_logger("spacegeo")


@dataclass(frozen=True)
class _Runner:
    """How to run one experiment kind: its config, experiment and report classes."""

    config: type[ValidationExperimentConfig]
    experiment: Callable[..., Any]
    report: Callable[[], Any]


_RUNNERS: dict[str, _Runner] = {
    "etas_baseline": _Runner(EtasExperimentConfig, EtasBaselineExperiment, EtasBaselineReport),
    "event_forecast": _Runner(EventForecastConfig, EventForecastExperiment, EventForecastReport),
    "small_trigger_etas": _Runner(SmallTriggerConfig, SmallTriggerExperiment, SmallTriggerReport),
    "anomaly_followup": _Runner(
        AnomalyFollowupConfig, AnomalyFollowupExperiment, AnomalyFollowupReport
    ),
}


class Cli:
    """Entry point; experiment configs choose their runner with ``experiment:``."""

    @classmethod
    def main(cls, argv: list[str] | None = None) -> int:
        """Parse arguments and run; returns the process exit code."""
        args = cls._parser().parse_args(argv)
        project = ProjectPaths.discover()
        config_path = (project.root / args.config).resolve()
        kind = (yaml.safe_load(config_path.read_text()) or {}).get("experiment")
        runner = _RUNNERS.get(str(kind))
        if runner is None:
            _log.error("Unknown experiment %r in %s (known: %s)", kind, config_path, list(_RUNNERS))
            return 2
        git = GitState.read(project.root)
        if git.dirty and not args.allow_dirty:
            _log.error("Working tree is dirty; commit first or pass --allow-dirty.")
            return 2
        return cls._run(runner, project, config_path, git)

    @staticmethod
    def _run(runner: _Runner, project: ProjectPaths, config_path: Path, git: GitState) -> int:
        config = runner.config.from_yaml(config_path)
        regions = {r.name: r.geo for r in RegionConfig.load_all(project.root / config.regions_file)}
        frames = [CatalogArchive(project.root / path).read() for path in config.catalog_paths]
        catalog = pd.concat(frames).sort_index()
        catalog = catalog.loc[~catalog["event_id"].duplicated(keep="last")]
        run = RunDirectory(project.runs, config_path.stem.replace("_", "-"), git, config.seed)
        result = runner.experiment(config, regions, catalog).run()
        runner.report().write(run, config, result)
        _log.info("Wrote %s\n%s", run.path, (run.path / "NOTES.md").read_text())
        return 0

    @staticmethod
    def _parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="spacegeo")
        sub = parser.add_subparsers(dest="command", required=True)
        run = sub.add_parser("run", help="Run an experiment config.")
        run.add_argument("config", type=Path)
        run.add_argument("--allow-dirty", action="store_true", help="Run on uncommitted code.")
        return parser


if __name__ == "__main__":
    sys.exit(Cli.main())
