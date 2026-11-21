---
name: add-feature
description: Use when adding or changing any model input in spacegeo (solar wind lags, Kp/Dst windows, dB/dt, CME geometry, seismicity history, spatial-graph features). Produces a Feature subclass with a stated physical rationale.
---

# Add a feature

Follow `add-component` for the general rules.

## Contract

The `Feature` base class owns the leakage guarantee: for each forecast time
`t` it passes your code only rows in `[t - lookback, t)`. You implement:

```python
@FEATURES.register("bz_min")
class BzMinimum(Feature):
    """Most negative IMF Bz in the lookback window.

    Rationale: southward Bz drives geomagnetic storms and therefore induced
    crustal currents; if space weather couples to faults, storm intensity
    is the first-order candidate.
    """

    input_columns = ("bz_nT",)

    @property
    def output_names(self) -> tuple[str, ...]:
        hours = int(self.lookback / duration(hours=1))
        return (f"bz_nT_min_{hours}h",)

    @classmethod
    def example(cls) -> Self:
        return cls(lookback=duration(hours=24))

    def _compute_window(self, window: pd.DataFrame, forecast_time: pd.Timestamp) -> Sequence[float]:
        return [float(window["bz_nT"].to_numpy().min())]
```

- **Rationale is mandatory** in the docstring: the mechanism this feature
  would capture if an effect existed. Features without one inflate multiple
  testing.
- Output names encode source, statistic, window and unit.
- No fitting inside a feature. Learned transforms belong to the model
  pipeline, fit on training data only.
- Don't override `compute` for speed unless the contract tests still pass;
  if you do, explain why in the docstring.

## Tests

- `tests/contracts/test_feature_contract.py` picks the class up
  automatically and checks leakage and output shape via `example()`.
- Add `tests/features/test_<group>.py` with a hand-computed tiny example.

## Record it

Add a line to `docs/features.md`: name, inputs, window, rationale.

## Red flags

- `.shift(-n)`, `bfill`, centred windows, `merge_asof` with
  `direction="forward"` or `allow_exact_matches=True`, anywhere upstream.
- Using a catalog value revised after the fact (final magnitudes) where a
  real-time forecaster would only have had preliminary values; note it.
