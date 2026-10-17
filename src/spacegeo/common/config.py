"""Typed, immutable configuration loaded from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from spacegeo.common.exceptions import ConfigError


class BaseConfig(BaseModel):
    """Base for every config object: frozen, and unknown keys are errors."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    @classmethod
    def from_yaml(cls, path: Path) -> Self:
        """Load and validate a config from a YAML file.

        Raises:
            ConfigError: If the file is unreadable or fails validation.
        """
        try:
            raw = yaml.safe_load(path.read_text())
            return cls.model_validate(raw or {})
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            raise ConfigError(f"Invalid config {path}: {exc}") from exc

    def to_yaml(self, path: Path) -> None:
        """Write the resolved config to YAML."""
        path.write_text(yaml.safe_dump(self.model_dump(mode="json"), sort_keys=False))
