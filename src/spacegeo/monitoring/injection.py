"""Detection power by synthetic injection into validation weeks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from spacegeo.common.stats import benjamini_hochberg
from spacegeo.models.base import CountModel


class InjectionStudy:
    """How often an extra burst of ``k`` events in one region gets flagged.

    For every scored region-week, the observed count is raised by ``k`` in
    that region only, its tail p-values are recomputed from the fitted
    model, and Benjamini-Hochberg is re-run over the whole week exactly as
    the live scan does. Power is the fraction of region-weeks where the
    region is then flagged ``excess``. No labels are needed: the injected
    burst is the ground truth.

    Args:
        models: Fitted count model per region (from the scanner).
        fdr: False-discovery rate used for flagging.
        sizes: Burst sizes (extra events per week) to inject.
    """

    def __init__(
        self,
        models: Mapping[str, CountModel],
        fdr: float = 0.05,
        sizes: Sequence[int] = (2, 5, 10, 20, 40),
    ) -> None:
        if not sizes or min(sizes) < 1:
            raise ValueError("Injection sizes must be positive integers.")
        self._models = models
        self._fdr = fdr
        self._sizes = tuple(sizes)

    def power(self, results: pd.DataFrame) -> pd.DataFrame:
        """Detection rate per region and burst size.

        Args:
            results: One test's scan output (``window_start``, ``region``,
                ``observed``, ``p_high``, ``p_low``).

        Returns:
            Frame indexed by (``region``, ``added``) with ``power`` and
            ``weeks``.
        """
        hits: dict[tuple[str, int], list[bool]] = {}
        for _, week in results.groupby("window_start", sort=True):
            for (region, k), hit in self._inject_week(week).items():
                hits.setdefault((region, k), []).append(hit)
        rows = [
            {"region": r, "added": k, "power": float(np.mean(v)), "weeks": len(v)}
            for (r, k), v in hits.items()
        ]
        return pd.DataFrame(rows).set_index(["region", "added"]).sort_index()

    def _inject_week(self, week: pd.DataFrame) -> dict[tuple[str, int], bool]:
        regions = week["region"].to_list()
        observed = week["observed"].to_numpy(dtype=np.int64)
        p_high = week["p_high"].to_numpy(dtype=np.float64)
        p_low = week["p_low"].to_numpy(dtype=np.float64)
        out: dict[tuple[str, int], bool] = {}
        for i, region in enumerate(regions):
            model = self._models[region]
            for k in self._sizes:
                high, low = p_high.copy(), p_low.copy()
                high[i] = model.survival(int(observed[i]) + k)
                low[i] = model.cdf(int(observed[i]) + k)
                q = benjamini_hochberg(np.concatenate([high, low]))
                out[(region, k)] = bool(q[i] <= self._fdr)
        return out

    @staticmethod
    def minimum_detectable(power: pd.DataFrame, target: float = 0.8) -> pd.Series:
        """Smallest injected size reaching ``target`` power, per region (NaN if none)."""
        reached = power.loc[power["power"] >= target].reset_index()
        smallest = reached.groupby("region")["added"].min()
        regions = power.index.get_level_values("region").unique()
        return smallest.reindex(regions).rename("min_detectable_added")
