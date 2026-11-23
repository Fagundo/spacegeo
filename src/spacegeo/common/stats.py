"""Shared statistical helpers (multiple-testing corrections, ...)."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def benjamini_hochberg(p_values: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """Benjamini-Hochberg adjusted p-values (q-values) controlling the FDR.

    Valid for independent or positively dependent tests. Reject hypotheses
    whose q-value is at most the chosen false-discovery rate.

    Args:
        p_values: Raw p-values in [0, 1], any shape (flattened internally).

    Returns:
        Adjusted p-values, same order as the input, each in [0, 1].

    Raises:
        ValueError: If any p-value is NaN or outside [0, 1].
    """
    p = np.asarray(p_values, dtype=np.float64).ravel()
    if np.isnan(p).any() or (p < 0).any() or (p > 1).any():
        raise ValueError("p-values must be in [0, 1] and not NaN.")
    n = p.size
    if n == 0:
        return p
    order = np.argsort(p)
    scaled = p[order] * n / np.arange(1, n + 1)
    monotone = np.minimum.accumulate(scaled[::-1])[::-1]
    adjusted = np.empty(n)
    adjusted[order] = np.clip(monotone, 0.0, 1.0)
    return adjusted
