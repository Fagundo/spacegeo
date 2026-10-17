"""Shared fitted-state tracking for stateful components."""

from __future__ import annotations

from spacegeo.common.exceptions import NotFittedError


class FittableMixin:
    """Tracks whether a component has been fitted.

    Subclasses call :meth:`_mark_fitted` at the end of ``fit`` and
    :meth:`_require_fitted` before using learned state.
    """

    _fitted: bool = False

    @property
    def is_fitted(self) -> bool:
        """Whether ``fit`` has completed."""
        return self._fitted

    def _mark_fitted(self) -> None:
        self._fitted = True

    def _require_fitted(self) -> None:
        if not self._fitted:
            raise NotFittedError(f"{type(self).__name__} must be fitted before use.")
