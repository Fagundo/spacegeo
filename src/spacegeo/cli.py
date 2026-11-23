"""``spacegeo`` command line: ``spacegeo run <config.yaml>``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from spacegeo.common.log import get_logger
from spacegeo.common.paths import ProjectPaths
from spacegeo.common.run import GitState, RunDirectory
from spacegeo.data.io.catalog_archive import CatalogArchive
from spacegeo.evaluation.anomaly import RegionConfig
from spacegeo.training.etas_baseline import EtasBaselineExperiment, EtasExperimentConfig
from spacegeo.training.etas_report import EtasBaselineReport
from spacegeo.training.event_forecast import EventForecastConfig, EventForecastExperiment
from spacegeo.training.event_forecast_report import EventForecastReport

_log = get_logger("spacegeo")


class Cli:
    """Entry point; experiment configs choose their runner with ``experiment:``."""

    RUNNERS = ("etas_baseline", "event_forecast")

    @classmethod
    def main(cls, argv: list[str] | None = None) -> int:
        """Parse arguments and run; returns the process exit code."""
        args = cls._parser().parse_args(argv)
        project = ProjectPaths.discover()
        config_path = (project.root / args.config).resolve()
        kind = (yaml.safe_load(config_path.read_text()) or {}).get("experiment")
        if kind not in cls.RUNNERS:
            _log.error("Unknown experiment %r in %s (known: %s)", kind, config_path, cls.RUNNERS)
            return 2
        git = GitState.read(project.root)
        if git.dirty and not args.allow_dirty:
            _log.error("Working tree is dirty; commit first or pass --allow-dirty.")
            return 2
        if kind == "event_forecast":
            return cls._run_event_forecast(project, config_path, git)
        return cls._run_etas(project, config_path, git)

    @staticmethod
    def _run_etas(project: ProjectPaths, config_path: Path, git: GitState) -> int:
        config = EtasExperimentConfig.from_yaml(config_path)
        regions = {r.name: r.geo for r in RegionConfig.load_all(project.root / config.regions_file)}
        catalog = CatalogArchive(project.root / config.catalog).read()
        run = RunDirectory(project.runs, config_path.stem.replace("_", "-"), git, config.seed)
        result = EtasBaselineExperiment(config, regions, catalog).run()
        EtasBaselineReport().write(run, config, result)
        _log.info("Wrote %s\n%s", run.path, (run.path / "NOTES.md").read_text())
        return 0

    @staticmethod
    def _run_event_forecast(project: ProjectPaths, config_path: Path, git: GitState) -> int:
        config = EventForecastConfig.from_yaml(config_path)
        regions = {r.name: r.geo for r in RegionConfig.load_all(project.root / config.regions_file)}
        catalog = CatalogArchive(project.root / config.catalog).read()
        run = RunDirectory(project.runs, config_path.stem.replace("_", "-"), git, config.seed)
        result = EventForecastExperiment(config, regions, catalog).run()
        EventForecastReport().write(run, config, result)
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
