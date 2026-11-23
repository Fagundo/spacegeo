# Ring of Fire weekly anomaly scan

Latest week: 2026-11-16 to 2026-11-23 (UTC, end exclusive).
Models fit on the training + validation span. `flag` = q <= FDR within the week.
Recent days are preliminary: USGS adds and revises events for weeks.

Validation verdict: activity: calibrated, mainshocks: calibrated. See `../validation/by_test.csv`.

## activity

| region | observed | expected | p_high | p_low | q_high | q_low | flag | max_mag |
|---|---|---|---|---|---|---|---|---|
| peru | 10 | 1.99 | 0.00815 | 0.992 | 0.153 | 1 |  | 6.7 |
| california_baja | 1 | 0.223 | 0.133 | 0.973 | 1 | 1 |  | 4.98 |
| chile | 7 | 5.91 | 0.235 | 0.85 | 1 | 1 |  | 5.1 |
| northern_andes | 2 | 1.43 | 0.385 | 0.836 | 1 | 1 |  | 4.8 |
| png_solomons | 10 | 10.9 | 0.395 | 0.67 | 1 | 1 |  | 5.8 |
| japan | 6 | 8.5 | 0.434 | 0.666 | 1 | 1 |  | 5.4 |
| kamchatka_kurils | 4 | 6.6 | 0.59 | 0.573 | 1 | 1 |  | 4.9 |
| new_zealand | 1 | 1.54 | 0.614 | 0.693 | 1 | 1 |  | 4.9 |
| alaska_aleutians | 2 | 3.26 | 0.69 | 0.559 | 1 | 1 |  | 5.2 |
| izu_bonin_marianas | 3 | 5.35 | 0.733 | 0.41 | 1 | 1 |  | 5.8 |
| indonesia | 12 | 17.6 | 0.734 | 0.334 | 1 | 1 |  | 6.8 |
| mexico | 1 | 1.95 | 0.764 | 0.53 | 1 | 1 |  | 4.8 |
| vanuatu_fiji | 8 | 13.5 | 0.782 | 0.301 | 1 | 1 |  | 5.1 |
| central_america | 1 | 2.57 | 0.86 | 0.354 | 1 | 1 |  | 4.5 |
| taiwan_philippines | 3 | 8.03 | 0.901 | 0.2 | 1 | 1 |  | 5.1 |
| tonga_kermadec | 3 | 15.7 | 0.995 | 0.00898 | 1 | 0.153 |  | 4.9 |
| cascadia | 0 | 0.567 | 1 | 0.687 | 1 | 1 |  |  |

## mainshocks

| region | observed | expected | p_high | p_low | q_high | q_low | flag | max_mag |
|---|---|---|---|---|---|---|---|---|
| california_baja | 1 | 0.111 | 0.105 | 0.994 | 0.891 | 1 |  | 4.98 |
| peru | 3 | 1.25 | 0.131 | 0.962 | 0.891 | 1 |  | 6.7 |
| png_solomons | 5 | 3.38 | 0.252 | 0.873 | 1 | 1 |  | 5 |
| alaska_aleutians | 2 | 1.44 | 0.42 | 0.825 | 1 | 1 |  | 5.2 |
| chile | 3 | 2.43 | 0.439 | 0.772 | 1 | 1 |  | 5.1 |
| japan | 3 | 2.43 | 0.439 | 0.772 | 1 | 1 |  | 5.4 |
| new_zealand | 1 | 0.734 | 0.52 | 0.832 | 1 | 1 |  | 4.9 |
| northern_andes | 1 | 0.994 | 0.63 | 0.738 | 1 | 1 |  | 4.8 |
| mexico | 1 | 1.02 | 0.641 | 0.727 | 1 | 1 |  | 4.8 |
| izu_bonin_marianas | 2 | 2.41 | 0.694 | 0.566 | 1 | 1 |  | 5.8 |
| vanuatu_fiji | 2 | 3.9 | 0.901 | 0.253 | 1 | 1 |  | 4.7 |
| kamchatka_kurils | 1 | 2.37 | 0.907 | 0.314 | 1 | 1 |  | 4.9 |
| tonga_kermadec | 2 | 4.97 | 0.958 | 0.127 | 1 | 0.891 |  | 4.9 |
| indonesia | 3 | 7.08 | 0.972 | 0.0777 | 1 | 0.891 |  | 6.8 |
| taiwan_philippines | 0 | 3.03 | 1 | 0.0481 | 1 | 0.891 |  |  |
| central_america | 0 | 1.17 | 1 | 0.31 | 1 | 1 |  |  |
| cascadia | 0 | 0.307 | 1 | 0.736 | 1 | 1 |  |  |

## All flagged region-weeks in the test period

| window_start | test | region | observed | expected | p_high | p_low | q_high | q_low | flag | max_mag |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-06-08 | activity | taiwan_philippines | 143 | 8.03 | 0.000737 | 0.999 | 0.0251 | 1 | excess | 6.5 |
| 2026-07-13 | activity | mexico | 55 | 1.95 | 0.000737 | 0.999 | 0.0125 | 1 | excess | 7.3 |
| 2026-07-13 | activity | central_america | 32 | 2.57 | 3.02e-11 | 1 | 1.03e-09 | 1 | excess | 7.3 |
| 2026-09-14 | activity | northern_andes | 18 | 1.43 | 0.000737 | 0.999 | 0.0251 | 1 | excess | 4.9 |
| 2026-10-05 | activity | central_america | 93 | 2.57 | 1.25e-27 | 1 | 2.12e-26 | 1 | excess | 7.7 |
| 2026-10-05 | activity | northern_andes | 90 | 1.43 | 2.12e-28 | 1 | 7.21e-27 | 1 | excess | 7.7 |
| 2026-10-12 | activity | central_america | 25 | 2.57 | 0.00147 | 0.999 | 0.0251 | 1 | excess | 6.1 |
| 2026-10-12 | activity | northern_andes | 22 | 1.43 | 0.000737 | 0.999 | 0.0251 | 1 | excess | 6.1 |
| 2026-07-27 | mainshocks | tonga_kermadec | 18 | 4.97 | 4.96e-06 | 1 | 0.000169 | 1 | excess | 5.9 |
| 2026-10-05 | mainshocks | central_america | 9 | 1.17 | 4.01e-06 | 1 | 0.000136 | 1 | excess | 7.7 |
| 2026-10-05 | mainshocks | northern_andes | 6 | 0.994 | 0.000577 | 1 | 0.00981 | 1 | excess | 7.7 |
