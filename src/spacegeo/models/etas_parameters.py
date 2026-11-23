"""Parameters and settings of the space-time ETAS model."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class EtasParameters:
    """Space-time ETAS parameters (Ogata 1998; Zhuang et al. 2002).

    Conditional intensity (events per day per km^2)::

        lambda(t, x) = mu * u(x)
                     + sum_{t_i < t} A e^{alpha (m_i - m0)}
                                     * (p - 1)/c * (1 + (t - t_i)/c)^(-p)
                                     * (q - 1)/(pi s_i) * (1 + r_i^2 / s_i)^(-q)
        s_i = D e^{gamma (m_i - m0)}

    Attributes:
        mu: Background rate over the whole region, events/day.
        a: Productivity: expected direct offspring of an M = m0 event.
        alpha: Productivity growth per magnitude unit (natural-log scale).
        c: Omori time offset, days.
        p: Omori decay exponent (> 1).
        d: Spatial scale of an M = m0 event's offspring, km^2.
        gamma: Spatial-scale growth per magnitude unit.
        q: Spatial decay exponent (> 1).
    """

    mu: float
    a: float
    alpha: float
    c: float
    p: float
    d: float
    gamma: float
    q: float

    NAMES = ("mu", "a", "alpha", "c", "p", "d", "gamma", "q")

    def __post_init__(self) -> None:
        positive = (self.mu, self.a, self.alpha, self.c, self.d, self.gamma)
        if min(positive) <= 0 or self.p <= 1 or self.q <= 1:
            raise ValueError(f"Invalid ETAS parameters: {self}.")

    def to_vector(self) -> npt.NDArray[np.float64]:
        """Unconstrained optimizer coordinates (logs; p and q via log(x - 1))."""
        return np.log(
            [self.mu, self.a, self.alpha, self.c, self.p - 1, self.d, self.gamma, self.q - 1]
        )

    @classmethod
    def from_vector(cls, theta: npt.ArrayLike) -> EtasParameters:
        """Inverse of :meth:`to_vector`."""
        mu, a, alpha, c, pm1, d, gamma, qm1 = np.exp(np.asarray(theta, dtype=np.float64))
        return cls(
            mu=float(mu),
            a=float(a),
            alpha=float(alpha),
            c=float(c),
            p=float(pm1 + 1),
            d=float(d),
            gamma=float(gamma),
            q=float(qm1 + 1),
        )

    def branching_ratio(self, beta: float) -> float:
        """Mean offspring per event for Gutenberg-Richter ``beta`` (inf if alpha >= beta)."""
        if self.alpha >= beta:
            return math.inf
        return self.a * beta / (beta - self.alpha)

    def as_dict(self) -> dict[str, float]:
        """Plain mapping, for logging and JSON."""
        return {k: float(v) for k, v in asdict(self).items()}


@dataclass(frozen=True)
class EtasSettings:
    """Fitting and truncation choices (fixed, not estimated).

    Attributes:
        m0: Reference / threshold magnitude (the catalog Mc).
        t_max_days: Triggering is truncated after this many days.
        r_max_km: Triggering is truncated beyond this distance, km.
        burn_in_days: Leading part of the fit window used only as history.
        iterations: Maximum background / parameter alternations
            (stochastic declustering steps).
        tolerance: Stop when no background probability moves more than this.
        n_bearings: Bearings used for the in-region share of each offspring
            kernel.
        step_km: March step when finding region exits, km.
        neighbors: Nearest-neighbour rank for background bandwidths.
        min_bandwidth_km: Smallest background bandwidth, km.
    """

    m0: float = 4.5
    t_max_days: float = 365.0
    r_max_km: float = 300.0
    burn_in_days: float = 365.0
    iterations: int = 5
    tolerance: float = 0.02
    n_bearings: int = 24
    step_km: float = 5.0
    neighbors: int = 5
    min_bandwidth_km: float = 10.0

    def initial(self, n_events: int, days: float) -> EtasParameters:
        """A neutral starting point for the optimizer."""
        return EtasParameters(
            mu=max(0.5 * n_events / days, 1e-4),
            a=0.3,
            alpha=1.5,
            c=0.01,
            p=1.1,
            d=50.0,
            gamma=1.0,
            q=1.5,
        )
