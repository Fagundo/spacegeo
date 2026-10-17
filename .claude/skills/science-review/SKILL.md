---
name: science-review
description: Use before merging any spacegeo change that touches targets, features, splits, declustering or evaluation, and before reporting any result. A checklist for the statistical traps that have sunk earlier space-weather/earthquake studies.
---

# Science review

Walk every item. For each, answer **pass / fail / n.a.** with one line of
evidence (file + line, test name, or plot). Report the list to the user.
Any fail blocks merge or blocks the claim.

## Leakage

- [ ] Every feature used has a passing no-future-data test.
- [ ] Splits are temporal, with a gap ≥ max(lookback, horizon).
- [ ] Scalers / fitted transforms are fit on training span only.
- [ ] No test-span data was read (check `docs/test-unlocks.md`).
- [ ] Aftershock sequences don't straddle the train/test boundary as
      positives.

## Seismicity

- [ ] Catalog declustered, or clustering modelled explicitly (ETAS).
      Method and parameters stated.
- [ ] Magnitude of completeness fixed per era; events below it dropped.
- [ ] Target defined per region, not "anywhere on Earth".
- [ ] Base rate of the target reported for each split.

## Baselines and metrics

- [ ] Compared against ETAS (or the agreed seismicity-only baseline), not
      just chance or climatology.
- [ ] Metric is a proper scoring rule or information gain, plus a
      calibration plot. Accuracy alone is not accepted.
- [ ] Uncertainty via block bootstrap over time (blocks ≥ longest
      autocorrelation scale, e.g. ~27-day solar rotation or longer).

## Space-weather confounds

- [ ] Solar-cycle trend handled (detrend, include cycle phase, or test that
      the result holds within cycle phases).
- [ ] Data gaps in OMNI/indices handled without forward-filling across them.
- [ ] Physical rationale stated for each space-weather feature.

## Multiple testing

- [ ] Count of all variants tried in this family (features, lags,
      thresholds, regions) recorded.
- [ ] Significance corrected for that count.
- [ ] Negative and null variants reported alongside the positive ones.

## Robustness (before any positive claim)

- [ ] Shuffle test: permute space-weather series in blocks; the "effect"
      should vanish.
- [ ] Holds on a different declustering method.
- [ ] Holds across sub-regions or time halves, or the dependence is
      explained.
