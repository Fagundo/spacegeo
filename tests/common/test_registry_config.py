from pathlib import Path

import pytest

from spacegeo.common.config import BaseConfig
from spacegeo.common.exceptions import ConfigError, RegistryError
from spacegeo.common.registry import Registry


class _Base:
    pass


def test_registry_roundtrip_and_errors() -> None:
    reg: Registry[_Base] = Registry("thing")

    @reg.register("a")
    class _A(_Base):
        pass

    assert reg.get("a") is _A
    assert "a" in reg
    assert reg.names() == ["a"]
    with pytest.raises(RegistryError, match="already registered"):
        reg.register("a")(_A)
    with pytest.raises(RegistryError, match="Unknown thing"):
        reg.get("b")


class _Cfg(BaseConfig):
    seed: int
    name: str = "x"


def test_config_yaml_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    _Cfg(seed=3).to_yaml(path)
    assert _Cfg.from_yaml(path) == _Cfg(seed=3)


def test_config_rejects_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text("seed: 1\ntypo: 2\n")
    with pytest.raises(ConfigError):
        _Cfg.from_yaml(path)
