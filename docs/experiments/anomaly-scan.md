# Experiment: weekly regional anomaly scan (Ring of Fire)

Written before the scan was run on real data (2026-11-23).

## Question

Each week, does any Ring of Fire region have significantly more (or fewer)
M>=4.5 earthquakes than its own history predicts?

This is seismicity-only monitoring. It uses no space-weather inputs and is
not a test of the project's primary hypothesis.

## Setup

- Data: USGS ComCat, `eventtype=earthquake`, M>=4.5 (`configs/ring_of_fire_scan.yaml`).
- Regions: 17 lat/lon boxes along the Pacific Ring of Fire (may overlap).
- Windows: Monday 00:00 UTC to the next Monday.
- Tests per region-week:
  - `activity`: Mc-cut catalog vs. the empirical distribution of the ~1040
    training weekly counts (P(N >= n) = fraction of past weeks with >= n).
  - `mainshocks`: causal Gardner-Knopoff declustering (aftershock windows
    only, so a week never depends on later events) vs. a Poisson rate.
- P-values: one-sided upper (`p_high`) and lower (`p_low`) tail. Within each
  week, Benjamini-Hochberg over all regions x both tails; `flag` at q <= 0.05.

## Split

| Span | Dates | Use |
|------|-------|-----|
| Train | 2000-01-01 to 2020-01-01 | Fit each region's count model |
| Validation | 2020-01-01 to 2026-01-01 | Calibration check only; nothing is tuned |
| Test | 2026-01-01 onward | Live weekly predictions; models refit on train + validation |

## Pre-registered success criterion (validation)

A test is **calibrated** if, over all validation region-weeks, both
`P(p_high <= 0.05)` and `P(p_low <= 0.05)` are at most 0.075 (1.5x nominal).
Discrete count tests are conservative, so well-calibrated tests usually sit
below 0.05.

Also reported, not pass/fail: flag rates after FDR, and total observed /
expected per test and region (drift or completeness changes since training).

## If a test fails calibration

Do not tune on validation. Report it in `results/anomaly/validation/`,
treat that test's flags as unreliable, and write down any change (e.g. a
different dispersion model, a shorter baseline) here as a new, dated version
before re-running.

## Design history

- 2026-11-23, before any real-data run: `activity` first used a negative
  binomial fitted by moments. On a simulated catalog with realistic
  aftershock sequences it failed this criterion (`p_high <= 0.05` in 24% of
  validation region-weeks): a few huge sequences inflate the variance and
  the fitted shape puts too little mass at typical counts. Replaced with the
  empirical distribution. No real validation data had been scored.

## Known limitations

- Weekly counts are small; the scan can only detect large departures.
- Flags are per week. Over a year of weeks, some false flags are expected.
- The newest days are incomplete in ComCat; the weekly job recomputes every
  2026 week so revisions are picked up.
- Mixed magnitude types (Mw, mb) and regional completeness differences.
