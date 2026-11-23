"""Probability models over a feature table (one row per region-week, say)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Self

import numpy as np
import numpy.typing as npt
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from spacegeo.models.base import TABULAR_EVENT_MODELS, TabularEventModel


@TABULAR_EVENT_MODELS.register("climatology")
class ClimatologyEventModel(TabularEventModel):
    """Historical event rate per group (e.g. per region): no dynamics at all.

    Args:
        group_column: Column that defines the groups.
        prior_rows: Pseudo-rows at the overall rate added to each group, so a
            group with no events does not get probability 0.
    """

    def __init__(self, group_column: str = "region", prior_rows: float = 1.0) -> None:
        self._group = group_column
        self._prior = prior_rows
        self._rates: dict[str, float] = {}
        self._overall = 0.0

    @classmethod
    def example(cls) -> Self:
        """Default instance for the contract tests."""
        return cls()

    def _fit(self, features: pd.DataFrame, targets: pd.Series) -> None:
        self._overall = float(targets.mean())
        table = pd.DataFrame({"g": features[self._group].astype(str), "y": targets.to_numpy()})
        sums = table.groupby("g")["y"].agg(["sum", "size"])
        rates = (sums["sum"] + self._prior * self._overall) / (sums["size"] + self._prior)
        self._rates = {str(k): float(v) for k, v in zip(sums.index, np.asarray(rates), strict=True)}

    def _predict_proba(self, features: pd.DataFrame) -> npt.ArrayLike:
        groups = features[self._group].astype(str)
        return np.array([self._rates.get(g, self._overall) for g in groups], dtype=np.float64)


@TABULAR_EVENT_MODELS.register("logistic")
class LogisticEventModel(TabularEventModel):
    """Logistic regression on a few columns (e.g. recalibrating an ETAS forecast).

    Missing values are replaced by the training mean of the column.

    Args:
        columns: Feature columns used.
        c: Inverse L2 regularization strength.
    """

    def __init__(self, columns: Sequence[str], c: float = 1.0) -> None:
        self._columns = list(columns)
        self._model = LogisticRegression(C=c, max_iter=1000)
        self._fill: dict[str, float] = {}

    @classmethod
    def example(cls) -> Self:
        """Default instance for the contract tests."""
        return cls(columns=["x1"])

    def _matrix(self, features: pd.DataFrame) -> npt.NDArray[np.float64]:
        return features[self._columns].fillna(self._fill).to_numpy(dtype=np.float64)

    def _fit(self, features: pd.DataFrame, targets: pd.Series) -> None:
        means = np.asarray(features[self._columns].mean(), dtype=np.float64)
        self._fill = {
            col: float(m) if np.isfinite(m) else 0.0
            for col, m in zip(self._columns, means, strict=True)
        }
        self._model.fit(self._matrix(features), targets.to_numpy())

    def _predict_proba(self, features: pd.DataFrame) -> npt.ArrayLike:
        return self._model.predict_proba(self._matrix(features))[:, 1]


@dataclass(frozen=True)
class BoostingParams:
    """Gradient-boosting hyperparameters (fixed in the config, not tuned).

    Attributes:
        max_iter: Boosting rounds.
        learning_rate: Shrinkage.
        max_depth: Maximum tree depth.
        min_samples_leaf: Minimum rows per leaf.
        l2_regularization: L2 penalty on leaf values.
        seed: Random seed.
    """

    max_iter: int = 200
    learning_rate: float = 0.05
    max_depth: int = 3
    min_samples_leaf: int = 50
    l2_regularization: float = 1.0
    seed: int = 0


@TABULAR_EVENT_MODELS.register("gradient_boosting")
class GradientBoostingEventModel(TabularEventModel):
    """Histogram gradient-boosted trees (the XGBoost / LightGBM family).

    Uses scikit-learn's ``HistGradientBoostingClassifier``: missing values
    are handled natively and ``categorical`` columns are treated as
    categories. No early stopping, so nothing is tuned on a random split.

    Args:
        exclude: Columns never used as features (identifiers, targets).
        categorical: Columns treated as categories.
        params: Hyperparameters.
    """

    def __init__(
        self,
        exclude: Sequence[str] = (),
        categorical: Sequence[str] = (),
        params: BoostingParams | None = None,
    ) -> None:
        p = params or BoostingParams()
        self._exclude = set(exclude)
        self._categorical = list(categorical)
        self._model = HistGradientBoostingClassifier(
            max_iter=p.max_iter,
            learning_rate=p.learning_rate,
            max_depth=p.max_depth,
            min_samples_leaf=p.min_samples_leaf,
            l2_regularization=p.l2_regularization,
            early_stopping=False,  # pyright: ignore[reportArgumentType] - stubs omit bool
            categorical_features="from_dtype",
            random_state=p.seed,
        )
        self._columns: list[str] = []
        self._categories: dict[str, list[str]] = {}

    @classmethod
    def example(cls) -> Self:
        """Default instance for the contract tests."""
        return cls(categorical=["region"], params=BoostingParams(max_iter=20, min_samples_leaf=5))

    @property
    def feature_names(self) -> list[str]:
        """Columns the model uses, in order."""
        self._require_fitted()
        return list(self._columns)

    def _frame(self, features: pd.DataFrame) -> pd.DataFrame:
        frame = pd.DataFrame(features[self._columns]).copy()
        for col in self._categorical:
            frame[col] = pd.Categorical(frame[col].astype(str), categories=self._categories[col])
        return frame

    def _fit(self, features: pd.DataFrame, targets: pd.Series) -> None:
        self._columns = [c for c in features.columns if c not in self._exclude]
        self._categories = {
            c: sorted(features[c].astype(str).unique().tolist()) for c in self._categorical
        }
        self._model.fit(self._frame(features), targets.to_numpy())

    def _predict_proba(self, features: pd.DataFrame) -> npt.ArrayLike:
        return self._model.predict_proba(self._frame(features))[:, 1]
