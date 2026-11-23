# ETAS baseline, Ring of Fire

Hypothesis: A space-time ETAS model fitted on 2000-2019 forecasts 2020-2025 M>=4.5 seismicity in each Ring of Fire region better than a time-independent smoothed-seismicity Poisson model fitted on the same span.
Success criterion: Primary: pooled information gain over all 17 regions > 0 with the 95% interval excluding 0. Secondary (reported, Holm-corrected across 17 regions): per-region gain > 0; time-rescaling residuals consistent with a unit Poisson process (KS test on transformed inter-event times); every fitted branching ratio < 1.

**Primary criterion MET.** Pooled information gain 1.762 nats/event (95% CI 1.393 to 2.199), 31841 validation events in 312 weeks.

- Regions with gain CI above 0: 17 of 17
- Regions whose time-rescaling KS test rejects (Holm, 0.05): 6
- Largest branching ratio: 37.02
- Variants in this family: 1

## Per region

| region | n_train | n_val | info_gain_per_event | info_gain_lo | info_gain_hi | branching_ratio | b_value | etas_p | etas_alpha | ks_p_holm |
|---|---|---|---|---|---|---|---|---|---|---|
| alaska_aleutians | 3498 | 922 | 2.567 | 1.573 | 3.301 | 0.626 | 1.002 | 1.134 | 1.408 | 0.012 |
| cascadia | 600 | 169 | 2.82 | 1.34 | 3.993 | 0.429 | 0.823 | 1.258 | 0.816 | 0.846 |
| california_baja | 230 | 73 | 4.782 | 2.368 | 6.526 | 0.716 | 0.997 | 1.135 | 1.454 | 0.592 |
| mexico | 2077 | 564 | 0.997 | 0.679 | 1.292 | 0.504 | 0.997 | 1.126 | 1.19 | 0.062 |
| central_america | 2386 | 722 | 0.773 | 0.591 | 0.995 | 0.576 | 1.167 | 1.051 | 1.726 | 0.846 |
| northern_andes | 1253 | 510 | 0.733 | 0.436 | 1.068 | 0.629 | 1.151 | 1.03 | 1.312 | 0 |
| peru | 2031 | 666 | 0.688 | 0.432 | 0.978 | 0.362 | 1.045 | 1.132 | 1.563 | 0.242 |
| chile | 6485 | 1534 | 0.584 | 0.413 | 0.843 | 0.725 | 1.112 | 1.097 | 1.663 | 0.062 |
| kamchatka_kurils | 4512 | 2650 | 4.007 | 0.977 | 5.094 | 0.619 | 1.17 | 1.137 | 1.22 | 0 |
| japan | 9494 | 2033 | 2.104 | 1.535 | 2.647 | 37.025 | 1.161 | 1.002 | 1.383 | 0.187 |
| izu_bonin_marianas | 5382 | 1867 | 1.908 | 1.203 | 2.853 | 0.617 | 1.377 | 1.107 | 1.055 | 0.062 |
| taiwan_philippines | 6740 | 3407 | 2.803 | 1.715 | 3.814 | 0.495 | 1.231 | 1.148 | 1.478 | 0 |
| indonesia | 17966 | 4562 | 1.004 | 0.801 | 1.245 | 1.671 | 1.16 | 1.027 | 1.484 | 0.187 |
| png_solomons | 11836 | 2881 | 1.237 | 0.907 | 1.654 | 0.612 | 1.063 | 1.154 | 1.496 | 0.088 |
| vanuatu_fiji | 7925 | 2692 | 2.418 | 1.261 | 3.518 | 0.721 | 1.004 | 1.198 | 1.63 | 0.001 |
| tonga_kermadec | 16609 | 6329 | 1.073 | 0.59 | 1.676 | 0.792 | 1.169 | 1.061 | 1.464 | 0 |
| new_zealand | 1451 | 260 | 2.336 | 0.646 | 3.769 | 0.642 | 1.248 | 1.132 | 1.692 | 0.088 |
## Reading the result

**Primary criterion met.** ETAS forecasts 2020-2025 better than the time-independent model in every region (all 17 intervals above 0). This is the expected sanity result for a clustering model: most of the gain comes in the weeks after large sequences. The biggest weekly gains were Kamchatka-Kurils in the week of 28 Jul 2025 (an M8.8 there on 29 Jul), Taiwan-Philippines in the week of 27 Nov 2023, Tonga-Kermadec in the week of 1 Mar 2021 (an M8.1 on 4 Mar) and Vanuatu-Fiji in the week of 8 Feb 2021.

**Secondary criteria, as pre-registered:**

- Per-region gain > 0 (Holm): met in 17 of 17.
- Time-rescaling residuals: the KS test rejects (Holm 0.05) in 6 regions: Alaska-Aleutians, Northern Andes, Kamchatka-Kurils, Taiwan-Philippines, Vanuatu-Fiji and Tonga-Kermadec. ETAS with one parameter set per region does not fully describe those catalogs. The most likely boring explanations are that productivity varies between sequences, and that early aftershocks are missing after large events (short-term incompleteness), which a fixed-parameter ETAS cannot follow.
- Every branching ratio < 1: **not met** as pre-registered. Japan (37.0) and Indonesia (1.67) exceed 1. Both have p close to 1 (1.002 and 1.027). The pre-registered ratio is the untruncated one, A beta/(beta - alpha), and with p near 1 most of that untruncated offspring count would fall beyond the 365-day truncation, so it is not identified by the data. The ratio implied within the model's own truncation (A x share of the Omori kernel inside 365 days x share inside 300 km x beta/(beta - alpha)) is 0.66 for Japan, 0.42 for Indonesia, and 0.17-0.66 for every region (added after seeing results; reported, not substituted for the pre-registered check).

**Other caveats.**

- The stochastic-declustering loop reached its 5-iteration cap in 15 of 17 regions without background probabilities settling to within 0.02. Parameters may still move slightly with more iterations.
- b-values range from 0.82 (Cascadia, 230 events) to 1.38 (Izu-Bonin-Marianas). Magnitude types are mixed.
- Variants in this family: 1, so no multiple-variant correction is needed beyond the Holm correction across regions.
- Before the pre-registration was written, two regions (New Zealand and Tonga-Kermadec) were scored on validation during a timing check. This is disclosed in the config.
