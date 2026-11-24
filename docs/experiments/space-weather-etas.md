# Experiment (pre-registered): does space weather modulate the ETAS background?

**Run 2026-11-24 on validation 2020-2025: null for all three mechanisms.**
Results: `docs/results/2026-11-24_space-weather-etas/` (code at 287f448).

| Mechanism | Gain, nats/event (95% CI) | Shift p (Holm) | Sustained rate change per 1 sd (95% CI) |
|-----------|---------------------------|----------------|------------------------------------------|
| Energy (Newell) | 6.9e-5 (-1.3e-5 to 1.6e-4) | 0.05 (0.15) | +1.0% (-1.4 to +2.9) |
| Variability (σBz) | 6.7e-5 (-1.6e-5 to 1.7e-4) | 0.15 (0.30) | +0.9% (-1.7 to +3.3) |
| Compression (Pdyn) | 1.5e-5 (-1.3e-5 to 5.3e-5) | 0.22 (0.30) | +0.3% (-2.8 to +3.0) |

31,841 validation events in 17 regions. For scale, ETAS itself gained 1.76
nats/event over smoothed Poisson on the same span: the best space-weather
term adds about 1/25,000 of that. Sustained elevated driving at any of the
1-16 day scales changes the M>=4.5 background rate by less than about 3% per
standard deviation. The geomagnetic-latitude test is not interpreted (no
detection); for the record, its correlations were negative (opposite to the
prediction). Exploratory: the joint model's interval just excludes 0
(1.2e-4, 95% CI 6e-6 to 2.5e-4; uncorrected, not a claim); the 64-day
variants were null, and compression+64d scored slightly worse than ETAS.

Written 2026-11-24 UTC, before any space-weather feature or model code existed
and before any space-weather series was compared with seismicity. Config:
`configs/space_weather_etas.yaml` (its `prereg` block is the binding text;
this page explains it).

## Question

Does recent solar-wind driving of the magnetosphere change the rate of
M>=4.5 earthquakes, beyond what ETAS already explains from past seismicity?

Prior: low. Stresses that space weather can put on faults (magnetic pressure
changes of ~1e-6 Pa at the surface, small induced telluric currents) are many
orders of magnitude below tidal (~1e3 Pa) and barometric (~1e3 Pa) loading,
and tidal triggering itself is only weakly detectable. The design aims for a
result that is informative either way: a detection that survives strict
controls, or an upper bound on how much space weather could change the rate.

## Mechanisms (one primary test each)

| Mechanism | Hourly input (OMNI2) | Why it might matter |
|-----------|----------------------|---------------------|
| Energy (E) | Newell coupling v^(4/3) B_T^(2/3) sin^(8/3)(θ/2), B_T = √(By²+Bz²), θ = atan2(By, Bz), GSM | Rate of solar-wind energy entering the magnetosphere; drives storms, ring current and induced ground currents. |
| Variability (V) | `sigma_bz_nT`, within-hour standard deviation of Bz | Turbulent, rapidly changing driving produces larger dB/dt and induced currents than steady driving of the same strength. |
| Compression (C) | `pdyn_nPa`, solar-wind dynamic pressure | Pressure pulses (CME and stream-interface shocks) compress the magnetosphere and cause sudden impulses in the ground field. |

## Temporal structure: a distributed lag over ~3 weeks

For each mechanism the hourly input x(t) is smoothed with exponential moving
averages of e-folding time τ = 1, 4 and 16 days, using only hours that ended
before the forecast time. Each smoothed series is divided by a 365-day
average of the same input and logged, so z_τ measures driving relative to the
current solar-cycle level, then standardised with training-span statistics:

    z_τ(t) = standardise( log EMA_τ[x](t) − log EMA_365d[x](t) )

The ETAS background for region r becomes

    μ_r(x, t) = c_r · μ_r^ETAS(x) · exp(β₁ z₁(t) + β₄ z₄(t) + β₁₆ z₁₆(t))

The three β's together describe a response curve over roughly the previous
three weeks (fast response, delayed response, slow build-up are all
expressible), and are tested together, so each mechanism is one hypothesis.

- **Gaps:** EMAs are gap-aware (weights renormalised over observed hours). If
  less than half the weight is observed, z = 0 at that time (the model falls
  back to plain ETAS). Nothing is forward-filled.
- **Shared across regions:** one set of β's for all 17 regions; per-region
  c_r absorbs the change in mean rate.
- **ETAS held fixed:** triggering parameters and spatial background come from
  the per-region baseline fit on 2000-2019 and are not refitted, so the
  space-weather term can only explain what ETAS leaves as background.

## Primary test and success criterion

For each mechanism separately:

1. Fit β (3) and c_r (17) on training events (2001-2019; 2000 is history).
2. Score the 2020-2025 validation span: pooled information gain per event G
   over ETAS.
3. **Circular-shift test:** shift the hourly input series by a random offset
   (uniform between 365 days and span − 365 days, wrapping over 2001-2025),
   recompute features, refit on training, rescore. 199 shifts give
   p = (1 + #{G_shift ≥ G}) / 200. Shifting keeps every property of the space
   weather series (autocorrelation, 27-day recurrence, storm statistics) and
   breaks only its alignment with the earthquakes.
4. **Detected** only if the Holm-adjusted p (3 mechanisms) < 0.05 **and**
   G > 0 with its 95% moving-block bootstrap interval excluding 0.

A null is reported as a null, with the 95% interval on the rate change per
1 sd of each z_τ (exp(β) − 1).

## Secondary (reported regardless, interpreted only after a detection)

- **Geomagnetic latitude:** induced ground currents are much stronger at high
  magnetic latitude, so a real effect should be larger there. Test: one-sided
  Spearman correlation between per-region information gain and |geomagnetic
  latitude| of the region centroid (centred dipole, IGRF-13 2020 pole
  80.65°N, 72.68°W).

## Exploratory (not used for any claim)

- All three mechanisms in one model (9 β's).
- A fourth smoothing scale, τ = 64 days, added to each mechanism.

Family size recorded in the config: 5 variants (3 primary + 2 exploratory).

## Data and splits

- ComCat M>=4.5, m0 = Mc = 4.5, 17 disjoint Ring of Fire regions, no
  declustering (ETAS models clustering).
- OMNI2 hourly from `data/space_weather/omni2`.
- Train 2000-2019 (2000 only as history for ETAS and the 365-day average),
  validation 2020-2025, test 2026+ locked. Validation features near
  2020-01-01 use 2019 space weather, as forecasts must; no validation
  earthquake enters any fit.
- Known data caveat: dynamic pressure is missing for ~12% of hours in
  2000-2002, so mechanism C has more z = 0 hours early in training.

## Not in scope

Ground magnetometer dB/dt (would be a new source), CME catalogs, live weekly
forecasting with space weather (OMNI lags real time by about a month), and
the locked test span until validation justifies unlocking it.
