# Ring of Fire weekly anomaly scan

Latest week: 2026-11-16 to 2026-11-23 (UTC, end exclusive).
Models fit on the training + validation span. `flag` = q <= FDR within the week.
Recent days are preliminary: USGS adds and revises events for weeks.

Validation verdict: activity: calibrated, mainshocks: calibrated. See `../validation/by_test.csv`.

## activity

| region | observed | expected | p_high | p_low | q_high | q_low | flag | max_mag |
|---|---|---|---|---|---|---|---|---|
| peru | 10 | 1.99 | 0.00815 | 0.992 | 0.277 | 1 |  | 6.7 |
| california_baja | 1 | 0.223 | 0.133 | 0.973 | 0.978 | 1 |  | 4.98 |
| chile | 7 | 5.91 | 0.235 | 0.85 | 0.978 | 0.997 |  | 5.1 |
| vanuatu_fiji | 7 | 7.83 | 0.347 | 0.738 | 0.978 | 0.978 |  | 5.1 |
| png_solomons | 10 | 10.9 | 0.395 | 0.67 | 0.978 | 0.978 |  | 5.8 |
| japan | 6 | 8.5 | 0.434 | 0.666 | 0.978 | 0.978 |  | 5.4 |
| new_zealand | 1 | 1.26 | 0.526 | 0.777 | 0.978 | 0.978 |  | 4.9 |
| kamchatka_kurils | 3 | 5.28 | 0.559 | 0.614 | 0.978 | 0.978 |  | 4.9 |
| northern_andes | 1 | 1.3 | 0.676 | 0.658 | 0.978 | 0.978 |  | 4.8 |
| alaska_aleutians | 2 | 3.26 | 0.69 | 0.559 | 0.978 | 0.978 |  | 5.2 |
| izu_bonin_marianas | 3 | 5.35 | 0.733 | 0.41 | 0.978 | 0.978 |  | 5.8 |
| indonesia | 11 | 16.6 | 0.748 | 0.321 | 0.978 | 0.978 |  | 6.8 |
| mexico | 1 | 1.95 | 0.764 | 0.53 | 0.978 | 0.978 |  | 4.8 |
| central_america | 1 | 2.29 | 0.833 | 0.406 | 0.997 | 0.978 |  | 4.5 |
| taiwan_philippines | 1 | 7.48 | 0.985 | 0.06 | 1 | 0.68 |  | 5.1 |
| tonga_kermadec | 5 | 16.9 | 0.989 | 0.0267 | 1 | 0.454 |  | 5.2 |
| cascadia | 0 | 0.567 | 1 | 0.687 | 1 | 0.978 |  |  |

## mainshocks

| region | observed | expected | p_high | p_low | q_high | q_low | flag | max_mag |
|---|---|---|---|---|---|---|---|---|
| california_baja | 1 | 0.111 | 0.105 | 0.994 | 1 | 1 |  | 4.98 |
| peru | 3 | 1.25 | 0.131 | 0.962 | 1 | 1 |  | 6.7 |
| png_solomons | 5 | 3.38 | 0.252 | 0.873 | 1 | 1 |  | 5 |
| alaska_aleutians | 2 | 1.44 | 0.42 | 0.825 | 1 | 1 |  | 5.2 |
| new_zealand | 1 | 0.552 | 0.424 | 0.894 | 1 | 1 |  | 4.9 |
| chile | 3 | 2.43 | 0.439 | 0.772 | 1 | 1 |  | 5.1 |
| japan | 3 | 2.43 | 0.439 | 0.772 | 1 | 1 |  | 5.4 |
| northern_andes | 1 | 0.893 | 0.59 | 0.775 | 1 | 1 |  | 4.8 |
| mexico | 1 | 1.02 | 0.641 | 0.727 | 1 | 1 |  | 4.8 |
| izu_bonin_marianas | 2 | 2.41 | 0.694 | 0.566 | 1 | 1 |  | 5.8 |
| tonga_kermadec | 4 | 5.58 | 0.807 | 0.345 | 1 | 1 |  | 5.2 |
| vanuatu_fiji | 1 | 1.97 | 0.86 | 0.415 | 1 | 1 |  | 4.7 |
| indonesia | 3 | 6.76 | 0.964 | 0.0954 | 1 | 1 |  | 6.8 |
| taiwan_philippines | 0 | 2.79 | 1 | 0.0613 | 1 | 1 |  |  |
| kamchatka_kurils | 0 | 1.8 | 1 | 0.166 | 1 | 1 |  |  |
| central_america | 0 | 1.06 | 1 | 0.346 | 1 | 1 |  |  |
| cascadia | 0 | 0.307 | 1 | 0.736 | 1 | 1 |  |  |

## All flagged region-weeks in the test period

| window_start | test | region | observed | expected | p_high | p_low | q_high | q_low | flag | max_mag |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-06-08 | activity | taiwan_philippines | 103 | 7.48 | 0.000738 | 0.999 | 0.0251 | 1 | excess | 6.5 |
| 2026-07-13 | activity | mexico | 55 | 1.95 | 0.000737 | 0.999 | 0.0251 | 1 | excess | 7.3 |
| 2026-09-14 | activity | northern_andes | 17 | 1.3 | 0.000737 | 0.999 | 0.0251 | 1 | excess | 4.9 |
| 2026-10-05 | activity | central_america | 93 | 2.29 | 2e-30 | 1 | 6.81e-29 | 1 | excess | 7.7 |
| 2026-07-27 | mainshocks | tonga_kermadec | 20 | 5.58 | 1.81e-06 | 1 | 6.15e-05 | 1 | excess | 5.9 |
| 2026-10-05 | mainshocks | central_america | 9 | 1.06 | 1.8e-06 | 1 | 6.12e-05 | 1 | excess | 7.7 |
| 2026-10-19 | mainshocks | vanuatu_fiji | 8 | 1.97 | 0.000986 | 1 | 0.0335 | 1 | excess | 6.8 |
