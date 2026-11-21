from pathlib import Path

import pytest

from spacegeo.common.exceptions import NotFittedError
from spacegeo.common.fitting import FittableMixin
from spacegeo.common.paths import ProjectPaths
from spacegeo.common.provenance import ProvenanceLog


def test_provenance_tracks_current_files(tmp_path: Path) -> None:
    log = ProvenanceLog(tmp_path)
    f = tmp_path / "a.csv"
    f.write_text("x")
    assert not log.is_current(f)
    log.record("https://example.org/a.csv", f)
    assert log.is_current(f)
    f.write_text("changed")
    assert not log.is_current(f)
    assert len(log.records()) == 1


def test_project_paths_discover(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    paths = ProjectPaths.discover(nested)
    assert paths.root == tmp_path.resolve()
    assert paths.raw_source("usgs") == tmp_path.resolve() / "data" / "raw" / "usgs"


def test_fittable_mixin() -> None:
    thing = FittableMixin()
    with pytest.raises(NotFittedError):
        thing._require_fitted()
    thing._mark_fitted()
    assert thing.is_fitted
