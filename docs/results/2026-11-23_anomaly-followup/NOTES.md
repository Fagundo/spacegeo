# Do anomaly flags precede M>=7 mainshocks?

Hypothesis: A region-week flagged excess by the mainshocks test is followed by an M>=7.0 mainshock (causal Gardner-Knopoff) in the same region within 30 days after the week ends more often than an unflagged region-week.
Success criterion: Primary: lower bound of the relative-risk interval > 1. Secondary, Holm-corrected together: activity excess flags; deficit flags for either test; 60-day horizon.

**Primary criterion NOT MET.** Mainshocks-excess flags: relative risk 0.00 (95% CI 0.00 to 0.00); 0 of 14 flagged region-weeks vs. 236 of 5205 unflagged were followed by a target.

## All comparisons

| comparison | primary | flagged_weeks | flagged_with_target | unflagged_weeks | unflagged_with_target | p_target_given_flag | p_target_given_no_flag | relative_risk | rr_lo | rr_hi | p_rr_le_1 | resamples_without_flags | brier_skill_vs_base_rate | p_holm_secondary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mainshocks_excess_30d | True | 14 | 0 | 5205 | 236 | 0 | 0.04534 | 0 | 0 | 0 | 1 | 0 | 0.0001274 | nan |
| activity_excess_30d | False | 14 | 0 | 5205 | 236 | 0 | 0.04534 | 0 | 0 | 0 | 1 | 0 | 0.0001274 | 1 |
| any_deficit_30d | False | 1 | 0 | 5218 | 236 | 0 | 0.04523 | 0 | 0 | 0 | 1 | 0.342 | 9.076e-06 | 1 |
| mainshocks_excess_60d | False | 14 | 0 | 5120 | 456 | 0 | 0.08906 | 0 | 0 | 0 | 1 | 0 | 0.0002665 | 1 |

## Base rate of the target

| span | region_weeks | base_rate |
|---|---|---|
| train | 17663 | 0.04716 |
| validation | 5236 | 0.04507 |

## Validation targets (62)

| time | region | mag | lat_deg | lon_deg |
|---|---|---|---|---|
| 2020-02-13 10:33:44.406000+00:00 | kamchatka_kurils | 7 | 45.62 | 149 |
| 2020-03-25 02:49:21.160000+00:00 | kamchatka_kurils | 7.5 | 48.96 | 157.7 |
| 2020-06-18 12:49:53.844000+00:00 | tonga_kermadec | 7.4 | -33.29 | -177.9 |
| 2020-06-23 15:29:04.350000+00:00 | mexico | 7.4 | 15.89 | -96.01 |
| 2020-07-17 02:50:22.178000+00:00 | png_solomons | 7 | -7.836 | 147.8 |
| 2020-07-22 06:12:44.810000+00:00 | alaska_aleutians | 7.8 | 55.07 | -158.6 |
| 2021-01-21 12:23:04.255000+00:00 | indonesia | 7 | 4.993 | 127.5 |
| 2021-02-10 13:19:55.530000+00:00 | vanuatu_fiji | 7.7 | -23.05 | 171.7 |
| 2021-02-13 14:07:49.797000+00:00 | japan | 7.1 | 37.73 | 141.8 |
| 2021-03-04 13:27:34.647000+00:00 | new_zealand | 7.3 | -37.48 | 179.5 |
| 2021-03-04 17:41:23.370000+00:00 | tonga_kermadec | 7.4 | -29.68 | -177.8 |
| 2021-03-04 19:28:33.178000+00:00 | tonga_kermadec | 8.1 | -29.72 | -177.3 |
| 2021-03-20 09:09:43.966000+00:00 | japan | 7 | 38.45 | 141.6 |
| 2021-07-29 06:15:49.188000+00:00 | alaska_aleutians | 8.2 | 55.36 | -157.9 |
| 2021-08-11 17:46:13.143000+00:00 | taiwan_philippines | 7.1 | 6.475 | 126.7 |
| 2021-09-08 01:47:47.437000+00:00 | mexico | 7 | 16.95 | -99.75 |
| 2021-10-02 06:29:17.897000+00:00 | vanuatu_fiji | 7.3 | -21.13 | 174.9 |
| 2021-11-28 10:52:14.579000+00:00 | northern_andes | 7.5 | -4.467 | -76.81 |
| 2021-12-14 03:20:23.809000+00:00 | indonesia | 7.3 | -7.603 | 122.2 |
| 2021-12-29 18:25:51.962000+00:00 | indonesia | 7.3 | -7.548 | 127.6 |
| 2022-03-16 14:36:30.997000+00:00 | japan | 7.3 | 37.71 | 141.6 |
| 2022-03-31 05:44:01.146000+00:00 | vanuatu_fiji | 7 | -22.59 | 170.4 |
| 2022-05-26 12:02:21.110000+00:00 | peru | 7.2 | -14.91 | -70.29 |
| 2022-07-27 00:43:26.871000+00:00 | taiwan_philippines | 7 | 17.52 | 120.8 |
| 2022-09-10 23:47:00.233000+00:00 | png_solomons | 7.6 | -6.294 | 146.5 |
| 2022-09-14 11:04:06.558000+00:00 | vanuatu_fiji | 7 | -21.19 | 170.3 |
| 2022-09-19 18:05:08.217000+00:00 | mexico | 7.6 | 18.46 | -103 |
| 2022-11-09 09:51:04.068000+00:00 | tonga_kermadec | 7 | -26.09 | 178.3 |
| 2022-11-11 10:48:46.710000+00:00 | tonga_kermadec | 7.3 | -19.29 | -172.1 |
| 2022-11-12 07:09:13.514000+00:00 | tonga_kermadec | 7 | -20.11 | -178.3 |
| 2022-11-22 02:03:06.891000+00:00 | png_solomons | 7 | -9.82 | 159.6 |
| 2023-01-08 12:32:42.372000+00:00 | vanuatu_fiji | 7 | -14.95 | 166.9 |
| 2023-01-09 17:47:35.037000+00:00 | indonesia | 7.6 | -7.059 | 130 |
| 2023-01-18 06:06:11.454000+00:00 | indonesia | 7 | 2.731 | 127 |
| 2023-03-16 00:56:00.149000+00:00 | tonga_kermadec | 7 | -30.17 | -176.2 |
| 2023-04-02 18:04:11.261000+00:00 | png_solomons | 7 | -4.323 | 143.2 |
| 2023-04-14 09:55:45.220000+00:00 | indonesia | 7 | -6.041 | 112 |
| 2023-04-24 20:00:57.265000+00:00 | indonesia | 7.1 | -0.8082 | 98.51 |
| 2023-05-10 16:02:00.334000+00:00 | tonga_kermadec | 7.6 | -15.63 | -174.5 |
| 2023-05-19 02:57:03.172000+00:00 | vanuatu_fiji | 7.7 | -23.21 | 170.7 |
| 2023-06-15 18:06:28.572000+00:00 | tonga_kermadec | 7.2 | -22.99 | -177.1 |
| 2023-07-16 06:48:21.158000+00:00 | alaska_aleutians | 7.2 | 54.39 | -160.8 |
| 2023-08-28 19:55:30.875000+00:00 | indonesia | 7.1 | -6.789 | 116.5 |
| 2023-11-08 04:53:49.631000+00:00 | indonesia | 7.1 | -6.416 | 129.5 |
| 2023-12-02 14:37:04.454000+00:00 | taiwan_philippines | 7.6 | 8.527 | 126.4 |
| 2023-12-07 12:56:30.184000+00:00 | vanuatu_fiji | 7.1 | -20.62 | 169.3 |
| 2024-01-01 07:10:09.476000+00:00 | japan | 7.5 | 37.49 | 137.3 |
| 2024-04-02 23:58:12.173000+00:00 | taiwan_philippines | 7.4 | 23.84 | 121.6 |
| 2024-06-28 05:36:36.902000+00:00 | peru | 7.2 | -15.83 | -74.45 |
| 2024-07-11 02:13:18.585000+00:00 | taiwan_philippines | 7.1 | 6.084 | 123.2 |
| 2024-07-19 01:50:48.571000+00:00 | chile | 7.4 | -23.08 | -67.84 |
| 2024-08-08 07:42:55.206000+00:00 | japan | 7.1 | 31.76 | 131.5 |
| 2024-08-17 19:10:26.820000+00:00 | kamchatka_kurils | 7 | 52.93 | 160.1 |
| 2024-12-05 18:44:21.110000+00:00 | cascadia | 7 | 40.37 | -125 |
| 2024-12-17 01:47:25.741000+00:00 | vanuatu_fiji | 7.3 | -17.69 | 168.1 |
| 2025-03-30 12:18:50.362000+00:00 | tonga_kermadec | 7 | -20.3 | -174.1 |
| 2025-07-16 20:37:41.667000+00:00 | alaska_aleutians | 7.3 | 54.57 | -160.5 |
| 2025-07-20 06:49:04.327000+00:00 | kamchatka_kurils | 7.4 | 52.83 | 160.7 |
| 2025-07-29 23:24:52.483000+00:00 | kamchatka_kurils | 8.8 | 52.49 | 160.2 |
| 2025-10-10 01:43:59.585000+00:00 | taiwan_philippines | 7.4 | 7.287 | 126.7 |
| 2025-12-06 20:41:49.288000+00:00 | alaska_aleutians | 7 | 60.31 | -139.5 |
| 2025-12-08 14:15:09.896000+00:00 | japan | 7.6 | 41 | 142.2 |

## Reading the result

**Null: no flagged week was followed by an M>=7 mainshock.** 0 of 14 mainshocks-excess region-weeks were followed by an M>=7 mainshock within 30 days. The rate after unflagged weeks was 4.5% (236 of 5,205). The secondary comparisons are the same: 0 of 14 activity flags, 0 of 1 deficit flag, and 0 of 14 at 60 days.

**The interval is uninformative, not proof of zero.** With no flagged hits, every bootstrap resample gives a relative risk of 0, so the printed interval (0 to 0) is degenerate. A plainer bound, added after seeing the result and not pre-registered: under no effect, 0 hits in 14 flagged weeks happens 52% of the time (0.955^14). The exact binomial 95% upper bound on P(target | flag) is 19%, a relative risk of about 4.2. So the data only rule out a strong effect (RR above roughly 4), as the pre-registration warned ("a null result here is weak evidence of absence").

**What the flags actually mark.** Several mainshocks flags fall in the very week of a great quake: Vanuatu-Fiji in the week of 8 Feb 2021 (an M7.7 on 10 Feb), Tonga-Kermadec in the week of 1 Mar 2021 (an M8.1 on 4 Mar), Taiwan-Philippines in the week of 4 Dec 2023 (an M7.6 on 2 Dec) and Kamchatka-Kurils in the week of 28 Jul 2025 (an M8.8 on 29 Jul). Those weeks flag because a big quake has just happened. Any M7 in the next month would be its aftershock, and aftershocks are excluded by design. The flags are mostly a sequence detector, not a precursor.

**The two tests flag different weeks:** 4 flagged weeks are shared, and 10 are unique to each test.
