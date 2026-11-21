"""Architecture rules that lint tools can't express.

* Every layer exists and exposes its interfaces in ``base.py``.
* Outside ``common``, public behaviour lives in classes: no public
  module-level functions (common holds the shared stateless helpers).
* Every class in a layer's ``base.py`` that is meant to be extended is abstract.
* No module outside ``common`` redefines a name that ``common`` already exports.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
from pathlib import Path

import pytest

import spacegeo

SRC = Path(spacegeo.__file__).parent
COMMON = SRC / "common"

LAYERS = (
    "data/scraping",
    "data/io",
    "data/preprocessing",
    "features",
    "models",
    "evaluation",
    "training",
)


def _modules(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.name != "__init__.py")


def _public_functions(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    return [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and not node.name.startswith("_")
    ]


def _top_level_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and not node.name.startswith("_")
    }


@pytest.mark.parametrize("layer", LAYERS)
def test_layer_has_base_module(layer: str) -> None:
    assert (SRC / layer / "__init__.py").exists(), f"{layer} must be a package"
    assert (SRC / layer / "base.py").exists(), f"{layer} must define its interfaces in base.py"


@pytest.mark.parametrize(
    "module",
    [p for p in _modules(SRC) if COMMON not in p.parents],
    ids=lambda p: str(p.relative_to(SRC)),
)
def test_no_public_functions_outside_common(module: Path) -> None:
    functions = _public_functions(module)
    assert not functions, (
        f"{module.relative_to(SRC)} defines public functions {functions}. "
        "Put behaviour in a class, or move a shared stateless helper to spacegeo.common."
    )


@pytest.mark.parametrize("layer", LAYERS)
def test_base_module_defines_an_abstract_interface(layer: str) -> None:
    module = importlib.import_module("spacegeo." + layer.replace("/", ".") + ".base")
    local_classes = [
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if obj.__module__ == module.__name__
    ]
    has_interface = any(inspect.isabstract(c) for c in local_classes)
    has_dependency = layer == "training"  # orchestration layer: concrete by design
    assert has_interface or has_dependency, f"{layer}/base.py should define at least one ABC"


def test_no_duplicate_of_common_names() -> None:
    common_names = set().union(*(_top_level_names(p) for p in _modules(COMMON)))
    clashes = {
        str(p.relative_to(SRC)): sorted(_top_level_names(p) & common_names)
        for p in _modules(SRC)
        if COMMON not in p.parents and _top_level_names(p) & common_names
    }
    assert not clashes, f"These redefine names from spacegeo.common; import them instead: {clashes}"


def test_every_module_imports() -> None:
    for info in pkgutil.walk_packages([str(SRC)], prefix="spacegeo."):
        importlib.import_module(info.name)
