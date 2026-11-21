"""Preprocessor interface and composable pipeline.

Steps such as magnitude-of-completeness cuts, regional filters and
declustering are :class:`Preprocessor` subclasses. Stateful steps learn in
:meth:`Preprocessor.fit` on the training span only, then apply anywhere.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Self

import pandas as pd

from spacegeo.common.fitting import FittableMixin
from spacegeo.common.registry import Registry


class Preprocessor(FittableMixin, ABC):
    """One transformation of a clean DataFrame.

    Stateless steps implement only :meth:`transform`; stateful steps also
    override :meth:`fit`, and must call ``self._mark_fitted()`` when done.
    """

    def fit(self, data: pd.DataFrame) -> Self:
        """Learn any state from ``data`` (training span only). Default: none."""
        del data
        self._mark_fitted()
        return self

    @abstractmethod
    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Apply the step. Must not mutate ``data``."""

    def fit_transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Fit on ``data`` then transform it."""
        return self.fit(data).transform(data)


class PreprocessingPipeline(Preprocessor):
    """Applies steps in order (composite)."""

    def __init__(self, steps: Sequence[Preprocessor]) -> None:
        self._steps = tuple(steps)

    @property
    def steps(self) -> tuple[Preprocessor, ...]:
        """The steps, in order."""
        return self._steps

    def fit(self, data: pd.DataFrame) -> Self:
        """Fit each step on the output of the previous one."""
        current = data
        for step in self._steps:
            current = step.fit_transform(current)
        self._mark_fitted()
        return self

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Run every step in order."""
        self._require_fitted()
        current = data
        for step in self._steps:
            current = step.transform(current)
        return current


PREPROCESSORS: Registry[Preprocessor] = Registry("preprocessor")
