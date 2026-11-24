# Small quakes as ETAS triggers: M3.0 vs. M4.5 catalog

Hypothesis: In sub-regions where ComCat is complete to M3.0, a space-time ETAS model fitted on M>=3.0 events (2000-2019) assigns higher likelihood to the 2020-2025 M>=4.5 events than an ETAS model fitted on M>=4.5 events only.
Success criterion: Primary: pooled information gain over the three sub-regions > 0 with the 95% interval excluding 0. Reported, not pass/fail: per-sub-region gains with intervals (Holm-corrected one-sided p), branching ratios of both models.

**Primary criterion MET.** Pooled information gain 0.480 nats/M>=4.5 event (95% CI 0.219 to 0.859), 389 scored events in 312 weeks.

- Regions with gain CI above 0: 1 of 3
- Largest branching ratio (either model): 35.91
- Variants in this family: 1

## Per region

| region | n_train_low | n_train | n_val | fraction_above_mc | info_gain_per_event | info_gain_lo | info_gain_hi | branching_small | branching_large | small_alpha | large_alpha |
|---|---|---|---|---|---|---|---|---|---|---|---|
| alaska_mainland | 13657 | 680 | 293 | 0.05 | 0.193 | -0.064 | 0.546 | 35.91 | 0.869 | 0.9 | 1.518 |
| cascadia_onshore | 2205 | 90 | 35 | 0.041 | 0.536 | -0.313 | 1.856 | 1.657 | 14.94 | 0.397 | 0.018 |
| california | 6406 | 148 | 61 | 0.023 | 1.826 | 0.788 | 3.814 | 3.552 | 0.701 | 1.26 | 1.507 |
## Reading the result

**Primary criterion met, but carried mostly by California.** Adding M3.0-4.5 quakes as triggers raised the likelihood of the 2020-2025 M>=4.5 quakes by 0.48 nats per event pooled (95% CI 0.22 to 0.86). Per sub-region:

- **California:** +1.83 nats per event (CI 0.79 to 3.81), 61 events; significant after Holm correction. It contributes about 60% of the pooled total.
- **Mainland Alaska:** +0.19 (CI -0.06 to 0.55), 293 events. Not significant.
- **Onshore Cascadia:** +0.54 (CI -0.31 to 1.86), only 35 events. Not significant.

**Where the gains and losses come from.** The largest gains are single California M4.5+ quakes in quiet weeks: the M3 model had seen recent small activity nearby and the M4.5 model had nothing to go on. The largest losses are in mainland Alaska during the weeks of the October 2020 and July 2021 large sequences. A likely boring cause is that small aftershocks go missing for days after a big quake (short-term incompleteness), so the M3 model under-counts triggers exactly when it matters. Another is that the share of events reaching M4.5 is not constant inside big sequences.

**Fit caveats, same as the Ring of Fire baseline.** Several fits have the Omori exponent p at or near 1, so the untruncated branching ratio is not identified: 35.9 for the Alaska M3 model, and 14.9 for the Cascadia M4.5 model, whose alpha also collapsed to 0.02 with only 90 training events. Both models had the same settings, so this does not favour either side, but the Cascadia reference model is weak.

**Other caveats.**

- Small events are mostly ML/Md and large ones mb/Mw. The empirical share of M>=3 events that reach M4.5 handles the average offset, not variation in it.
- One variant, so no family-wise correction beyond the Holm correction across sub-regions.
- The sub-regions and low_m0 = 3.0 were chosen from training-span completeness only, before either model was fitted (disclosed in the config).
