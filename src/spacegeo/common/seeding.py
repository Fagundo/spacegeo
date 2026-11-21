"""Reproducible randomness."""

from __future__ import annotations

import random

import numpy as np


def seed_everything(seed: int) -> np.random.Generator:
    """Seed Python's and NumPy's global RNGs and return a fresh Generator.

    Prefer passing the returned Generator explicitly over relying on
    global state.
    """
    random.seed(seed)
    np.random.seed(seed)
    return np.random.default_rng(seed)
