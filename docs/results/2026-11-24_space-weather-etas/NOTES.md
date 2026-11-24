# ETAS + space-weather background, Ring of Fire

Hypothesis: Recent solar-wind driving of the magnetosphere modulates the background rate of M>=4.5 earthquakes: adding a space-weather term to the ETAS background improves out-of-sample forecasts. Three mechanisms are tested separately: (E) energy input, Newell coupling v^(4/3) B_T^(2/3) sin^(8/3)(theta/2); (V) solar-wind variability, OMNI within-hour sigma of Bz; (C) magnetospheric compression, solar-wind dynamic pressure.
Success criterion: A mechanism counts as detected only if both hold: (1) circular-shift test: p = (1 + #{G_shift >= G}) / 200 from 199 random circular shifts of the hourly feature series over 2001-2025 (offsets uniform in [365 days, span - 365 days]; b and c_r refitted on training for each shift), Holm-adjusted across the three mechanisms, < 0.05; and (2) G > 0 with its 95% moving-block bootstrap interval (13-week blocks, same weeks in every region) excluding 0. Otherwise the result is a null, reported as the 95% interval on the rate change per 1 sd of each z_tau. Secondary, reported regardless and interpreted only if a mechanism is detected: Spearman correlation between per-region information gain and |geomagnetic latitude| of the region centroid (centred dipole, IGRF-13 2020 pole 80.65 N, 72.68 W), one-sided, predicting a larger effect at high magnetic latitude.

**No mechanism detected (null).** The pre-registered criterion is not met.

## Variants (gain in nats/event over ETAS, validation 2020-01-01 to 2026-01-01)

| variant | info_gain_per_event | info_gain_lo | info_gain_hi | p_shift | p_shift_holm | detected | maglat_spearman_rho | maglat_spearman_p |
|---|---|---|---|---|---|---|---|---|
| energy | 0.0001 | -0 | 0.0002 | 0.05 | 0.15 | False | -0.2451 | 0.8285 |
| variability | 0.0001 | -0 | 0.0002 | 0.15 | 0.3 | False | -0.7083 | 0.9993 |
| compression | 0 | -0 | 0.0001 | 0.22 | 0.3 | False | -0.5588 | 0.9901 |
| joint | 0.0001 | 0 | 0.0002 | nan | nan | False | -0.4289 | 0.9571 |
| energy+64d | 0 | -0.0001 | 0.0001 | nan | nan | False | 0.0294 | 0.4554 |
| variability+64d | 0 | -0.0001 | 0.0001 | nan | nan | False | 0.2647 | 0.1523 |
| compression+64d | -0.0002 | -0.0004 | -0 | nan | nan | False | -0.1642 | 0.7356 |

## Rate change per 1 sd of each covariate (training fit, 95% interval)

Each value holds the other scales fixed. The scales are correlated, so
single coefficients can be large with opposite signs; the sustained
change (all scales of a variant up 1 sd together) is the stabler summary.

- energy: sustained +1.0% [-1.4, +2.9]; newell 1 d +1.4% [-0.7, +3.3]; newell 4 d -0.8% [-4.1, +3.1]; newell 16 d +0.4% [-3.6, +3.7]
- variability: sustained +0.9% [-1.7, +3.3]; sigma_bz_nT 1 d +0.8% [-1.3, +2.7]; sigma_bz_nT 4 d -0.4% [-3.7, +4.0]; sigma_bz_nT 16 d +0.5% [-4.5, +4.7]
- compression: sustained +0.3% [-2.8, +3.0]; pdyn_nPa 1 d +0.2% [-1.7, +2.2]; pdyn_nPa 4 d -0.2% [-3.8, +4.0]; pdyn_nPa 16 d +0.2% [-5.0, +5.0]
- joint: sustained +1.0% [-2.4, +3.5]; newell 1 d +1.3% [-1.3, +3.8]; newell 4 d -0.5% [-4.6, +4.1]; newell 16 d +0.1% [-5.2, +4.9]; pdyn_nPa 1 d -0.4% [-2.8, +2.4]; pdyn_nPa 4 d -0.1% [-4.8, +4.2]; pdyn_nPa 16 d -0.1% [-6.0, +6.6]; sigma_bz_nT 1 d +0.8% [-2.1, +3.6]; sigma_bz_nT 4 d -0.7% [-5.6, +5.1]; sigma_bz_nT 16 d +0.7% [-6.3, +7.5]
- energy+64d: sustained +0.7% [-2.0, +3.0]; newell 1 d +1.8% [-0.4, +3.6]; newell 4 d -2.0% [-5.6, +2.6]; newell 16 d +2.5% [-4.2, +8.4]; newell 64 d -1.6% [-5.9, +3.5]
- variability+64d: sustained +0.5% [-2.3, +3.4]; sigma_bz_nT 1 d +1.2% [-0.8, +3.0]; sigma_bz_nT 4 d -1.8% [-5.5, +3.3]; sigma_bz_nT 16 d +3.3% [-4.8, +10.0]; sigma_bz_nT 64 d -2.1% [-7.3, +3.8]
- compression+64d: sustained -0.4% [-4.1, +2.8]; pdyn_nPa 1 d +1.0% [-1.0, +2.9]; pdyn_nPa 4 d -2.7% [-6.9, +1.9]; pdyn_nPa 16 d +5.5% [-2.3, +13.3]; pdyn_nPa 64 d -3.9% [-9.0, +2.0]

## Notes

- Variants in this family: 5 (primary: 3, Holm across them).
- Shift test wraps the hourly grid from the end of the ETAS burn-in (2000-12-31) to 2026-01-01.
- Beta intervals: 500 refits on moving-block resamples of 7-day blocks of the fit span.
- Missing covariate hours (set to 0): newell_logratio_1d_vs_365d 0.1%, newell_logratio_4d_vs_365d 0.0%, newell_logratio_16d_vs_365d 0.0%, sigma_bz_nT_logratio_1d_vs_365d 0.0%, sigma_bz_nT_logratio_4d_vs_365d 0.0%, sigma_bz_nT_logratio_16d_vs_365d 0.0%, pdyn_nPa_logratio_1d_vs_365d 1.2%, pdyn_nPa_logratio_4d_vs_365d 0.2%, pdyn_nPa_logratio_16d_vs_365d 0.0%

## Per region

| region | n_val | geomagnetic_lat_deg | gain[energy] | gain[variability] | gain[compression] | gain[joint] | gain[energy+64d] | gain[variability+64d] | gain[compression+64d] |
|---|---|---|---|---|---|---|---|---|---|
| alaska_aleutians | 922 | 55.96 | -0.0004 | -0.0003 | -0.0001 | -0.0006 | -0.0003 | 0.0001 | -0.0003 |
| cascadia | 169 | 50.59 | -0.0011 | -0.0007 | -0.0003 | -0.0014 | -0.0008 | -0.0006 | -0.0007 |
| california_baja | 73 | 40.52 | -0.0001 | -0.0003 | -0.0002 | -0.0004 | 0.0006 | 0.0001 | -0.0006 |
| mexico | 564 | 29.3 | 0.0003 | 0.0001 | 0.0001 | -0.0001 | 0.0004 | -0 | 0 |
| central_america | 722 | 20.14 | -0.0002 | -0.0001 | -0.0001 | 0.0001 | -0.0003 | -0.0001 | -0.0001 |
| northern_andes | 510 | 11.63 | 0.0003 | 0.0005 | 0.0002 | 0.0004 | 0.0001 | -0.0004 | -0.0001 |
| peru | 666 | -3.158 | -0.0002 | 0.0001 | -0 | 0.0001 | -0.0006 | -0.0006 | -0.0009 |
| chile | 1534 | -23.15 | -0.0001 | 0 | 0 | 0.0001 | -0.0003 | -0 | -0.0006 |
| kamchatka_kurils | 2650 | 44.35 | -0.0001 | -0.0001 | 0 | -0.0002 | -0.0001 | -0.0001 | -0 |
| japan | 2033 | 29.79 | 0.0001 | 0 | -0 | 0.0001 | -0.0001 | 0 | -0.0002 |
| izu_bonin_marianas | 1867 | 12.28 | 0.0003 | 0.0002 | 0.0001 | 0.0004 | 0.0003 | 0.0003 | -0.0004 |
| taiwan_philippines | 3407 | 6.445 | 0 | 0 | 0 | 0.0001 | -0.0001 | -0.0001 | -0.0002 |
| indonesia | 4562 | -12.28 | 0.0001 | 0.0001 | 0 | 0.0002 | 0.0001 | 0.0001 | -0 |
| png_solomons | 2881 | -12.82 | 0.0001 | 0.0001 | 0.0001 | 0.0001 | 0.0003 | 0.0003 | 0.0004 |
| vanuatu_fiji | 2692 | -20.86 | 0.0003 | 0.0002 | 0 | 0.0004 | 0.0002 | -0 | -0.0003 |
| tonga_kermadec | 6329 | -27.3 | 0.0001 | 0.0001 | -0 | 0.0002 | 0 | -0.0001 | -0.0006 |
| new_zealand | 260 | -45.8 | 0.0003 | -0.0002 | -0.0001 | 0.0003 | 0.0009 | 0.0006 | -0.0004 |
