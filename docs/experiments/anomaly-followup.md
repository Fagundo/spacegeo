# Experiment (pre-registered): do anomaly flags precede large quakes?

**Run 2026-11-23 on validation 2020-2025: null.** 0 of 14 flagged region-weeks
were followed by an M>=7 mainshock (base rate 4.5%); only a relative risk above
about 4 can be ruled out. See `docs/results/2026-11-23_anomaly-followup/`.
The test-span confirmation (2026+) is still pending.

Written 2026-11-23, before any real-data scan has been run.

## Question

Is a region-week flagged `excess` by the weekly scan followed by a large
mainshock in the same region more often than an unflagged region-week?

This is a seismicity-only question. A positive answer would mostly
rediscover known clustering (foreshock-like behaviour), so it is a step
towards, not a substitute for, a comparison against ETAS.

## Definitions

- **Flag:** `flag == "excess"` from `results/anomaly/validation/weekly.csv.gz`
  (models fit on 2000-2019, frozen).
- **Target:** an M >= 7.0 mainshock (causal Gardner-Knopoff declustering, as
  in the `mainshocks` test) inside the same region box within 30 days after
  the end of the flagged week. Events inside the flagged week itself do not
  count, and aftershocks never count, so a sequence cannot predict itself.
- **Unit:** region-week.

## Primary hypothesis and test

- **Primary (one test):** `mainshocks` excess flags.
  H0: P(target | flag) = P(target | no flag).
- **Metric:** relative risk RR = P(target | flag) / P(target | no flag), plus
  the Brier skill score of the two-level forecast against the base rate.
- **Interval:** 95% moving-block bootstrap over weeks (13-week blocks), since
  30-day horizons from consecutive weeks overlap.
- **Success criterion:** lower bound of the RR interval > 1.

## Secondary (Holm-corrected together)

- `activity` excess flags.
- `deficit` flags (quiescence) for either test.
- 60-day horizon.

## Data and split

- Primary evaluation: validation span 2020-2025 (nothing was tuned on it for
  this question). Confirmation: the live 2026+ span, reported once two full
  years have accumulated, with the same definitions.
- Base rate of the target reported for train, validation and test.

## Power, stated up front

Validation has about 5,300 region-weeks. On simulated data the FDR flag rate
was about 0.1-0.2%, so expect roughly 5-25 flagged region-weeks. With a base
rate of a few percent, only a very large relative risk (around 5 or more)
can reach significance. A null result here is weak evidence of absence.

## Not allowed

- Changing the M7.0 / 30-day definitions after seeing results.
- Choosing regions after seeing which ones work.
- Claiming information beyond seismicity without an ETAS comparison.
