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


def block_bootstrap_ci(
    values: npt.ArrayLike,
    block_length: int,
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> tuple[float, float]:
    """Moving-block bootstrap confidence interval for the mean of a series.

    Resamples overlapping blocks of consecutive values so that
    autocorrelation shorter than ``block_length`` is preserved.

    Args:
        values: Time-ordered 1-D series (e.g. one value per week).
        block_length: Block size in samples; at least the autocorrelation
            scale (e.g. 13 weeks for a quarter).
        n_resamples: Number of bootstrap resamples.
        confidence: Two-sided coverage, e.g. 0.95.
        seed: RNG seed.

    Returns:
        ``(low, high)`` percentile bounds of the resampled means.

    Raises:
        ValueError: If the series is shorter than one block or has NaNs.
    """
    x = np.asarray(values, dtype=np.float64).ravel()
    if x.size < block_length or block_length < 1:
        raise ValueError(f"Need at least one block of {block_length} values, got {x.size}.")
    if not np.isfinite(x).all():
        raise ValueError("block_bootstrap_ci needs finite values.")
    rng = np.random.default_rng(seed)
    n_blocks = -(-x.size // block_length)
    starts = rng.integers(0, x.size - block_length + 1, size=(n_resamples, n_blocks))
    idx = (starts[..., None] + np.arange(block_length)).reshape(n_resamples, -1)[:, : x.size]
    means = x[idx].mean(axis=1)
    tail = (1 - confidence) / 2 * 100
    low, high = np.percentile(means, [tail, 100 - tail])
    return float(low), float(high)
