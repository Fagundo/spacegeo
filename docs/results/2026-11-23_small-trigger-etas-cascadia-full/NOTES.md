# Small quakes as ETAS triggers: M3.0 vs. M4.5 catalog

Hypothesis: Over the full Cascadia region (39-52N, 132-119W), ETAS fitted on M>=3.0 events assigns higher likelihood to 2020-2025 M>=4.5 events than ETAS fitted on M>=4.5 events only. Exploratory; not a test of the primary hypothesis.
Success criterion: Exploratory, reported descriptively: information gain and its 95% interval. With two variants now in this family, the primary result's interval would need a Bonferroni level of 0.025 per variant to keep a family-wise 0.05; noted for the record.

**Primary criterion NOT MET.** Pooled information gain -0.094 nats/M>=4.5 event (95% CI -0.397 to 0.424), 169 scored events in 312 weeks.

- Regions with gain CI above 0: 0 of 1
- Largest branching ratio (either model): 0.82
- Variants in this family: 2

## Per region

| region | n_train_low | n_train | n_val | fraction_above_mc | info_gain_per_event | info_gain_lo | info_gain_hi | branching_small | branching_large | small_alpha | large_alpha |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cascadia_full | 4664 | 600 | 169 | 0.129 | -0.094 | -0.397 | 0.424 | 0.816 | 0.429 | 0.507 | 0.816 |
## Reading the result (exploratory)

This run is exploratory (variant 2 of the family). "Primary criterion" above is the template's wording; nothing here was pre-registered as a pass/fail test.

**No detectable benefit over the full region:** -0.09 nats per M>=4.5 event (95% CI -0.40 to +0.42), 169 events. That compares with +0.54 (CI -0.31 to +1.86) for the onshore part alone.

**Why this is expected, and uninformative.** Offshore, small quakes are mostly missing. In the full region, 12.9% of training M>=3.0 events reach M4.5, against 4.1% onshore; with complete recording and b ~1, the share would be about 3%. So the M3 model sees most offshore M4.5+ quakes with few of the small triggers around them, and it pays for its extra parameters without the extra information. Adding offshore data mostly adds incompleteness, not small-quake signal.

Fits here are well behaved: branching ratios 0.82 (M3 model) and 0.43 (M4.5 model), both below 1.
