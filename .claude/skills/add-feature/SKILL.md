---
name: add-feature
description: Use when adding or changing any model input in spacegeo (solar wind lags, Kp/Dst windows, CME geometry, seismicity history, spatial-graph features). Every feature must ship with a test proving it uses no future data.
---

# Add a feature

Goal: a feature that is correct, unit-labelled, and provably free of
look-ahead leakage.

## Contract

Every feature is a pure function:

```python
def feature_name(
    data: pd.DataFrame,          # UTC-indexed source data
    forecast_times: pd.DatetimeIndex,  # UTC times we forecast from
    *,
    lookback: pd.Timedelta,
    # other parameters, all explicit
) -> pd.Series | pd.DataFrame:   # indexed by forecast_times
    ...
```

- Value at forecast time `t` uses only rows with timestamp **strictly < t**.
- Output is indexed by `forecast_times`, one row each, NaN where the lookback
  window lacks enough data (state the minimum coverage rule).
- Name output columns with the source, statistic, window and unit:
  `bz_nT_min_24h`, `kp_max_72h`, `pdyn_nPa_mean_12h`.
- No fitting inside feature functions. Anything learned (scalers, PCA) goes
  in the model pipeline and is fit on training data only.

## Steps

1. **State the physical rationale** in the docstring: what mechanism this
   feature would capture if an effect existed (e.g. induced crustal currents
   → use dB/dt, not raw B). Features without a stated rationale are noise
   that inflates multiple testing.
2. Implement in `src/spacegeo/features/<group>.py`.
3. **Mandatory leakage test** in `tests/features/test_<group>.py`:
   - Build synthetic data; compute the feature at some `t`.
   - Perturb or delete every row with timestamp `>= t`.
   - Assert the feature value at `t` is unchanged.
   - Include an edge case with a source row exactly at `t`.
4. Add a correctness test on a hand-computed tiny example.
5. Register the feature in the feature registry/config so experiments can
   select it by name. Record it in `docs/features.md` with rationale.
6. Run `uv run ruff format && uv run ruff check && uv run pyright && uv run pytest`.

## Red flags — stop and rethink

- `rolling(...)` without `closed="left"` or an explicit shift.
- `merge_asof` without `allow_exact_matches=False` and `direction="backward"`.
- Any use of `.shift(-n)`, `bfill`, or centered windows.
- Using a catalog field revised after the fact (e.g. final magnitudes) where a
  real-time forecaster would only have had preliminary values; note it.

## Done when

- Feature, leakage test, correctness test and docs entry are merged.
