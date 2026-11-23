# Weekly M>=6 forecast: gradient boosting vs. ETAS

Hypothesis: A gradient-boosted tree model (scikit-learn HistGradientBoosting, the XGBoost family) using seismicity-history features plus the ETAS forecast gives better probabilities for "at least one M>=6.0 in the region during the coming Monday-to-Monday week" than the ETAS forecast alone, recalibrated by logistic regression on the training span.
Success criterion: Primary: information gain of gradient boosting over ETAS-recalibrated > 0 with the 95% interval excluding 0, on validation weeks 2020-2025. Reported, not pass/fail: gain over climatology and over raw ETAS for every model, Brier skill score, ROC AUC, reliability table, the same comparison for M>=7.0 targets, and permutation importance of the boosting features.

**Primary criterion NOT MET.** Gain of gradient boosting over ETAS-recalibrated: -0.0003 nats per region-week (95% CI -0.0022 to 0.0017); base rate 0.090, 5304 validation region-weeks.

## Scores

| target | model | mean_log_score | gain_vs_etas_recalibrated | gain_vs_etas_recalibrated_lo | gain_vs_etas_recalibrated_hi | gain_vs_climatology | brier_skill_vs_climatology | roc_auc | base_rate |
|---|---|---|---|---|---|---|---|---|---|
| y_primary | etas_raw | -0.2763 | -0.0008663 | -0.003149 | 0.001077 | 0.001346 | 0.00841 | 0.7319 | 0.0905 |
| y_primary | climatology | -0.2777 | -0.002213 | -0.005035 | -0.000229 | 0 | 0 | 0.7269 | 0.0905 |
| y_primary | etas_recalibrated | -0.2755 | 0 | 0 | 0 | 0.002213 | 0.008867 | 0.7319 | 0.0905 |
| y_primary | gradient_boosting | -0.2757 | -0.0002727 | -0.002173 | 0.001724 | 0.00194 | 0.009113 | 0.7314 | 0.0905 |
| y_secondary | etas_raw | -0.06345 | -0.00198 | -0.003874 | -0.0002008 | -0.001743 | -0.002937 | 0.6945 | 0.01188 |
| y_secondary | climatology | -0.0617 | -0.0002374 | -0.001714 | 0.001104 | 0 | 0 | 0.7046 | 0.01188 |
| y_secondary | etas_recalibrated | -0.06147 | 0 | 0 | 0 | 0.0002374 | 0.0003 | 0.6945 | 0.01188 |
| y_secondary | gradient_boosting | -0.06385 | -0.002386 | -0.004709 | -9.366e-05 | -0.002149 | -0.005767 | 0.6327 | 0.01188 |

## Permutation importance (gradient boosting, validation)

| feature | log_loss_increase |
|---|---|
| log_etas_count_y_primary | 0.03043 |
| log_etas_count_m0 | 0.004338 |
| log1p_days_since_M6 | 0.003406 |
| region | 0.003307 |
| count_M4.5_365d | 0.00315 |
| max_mag_30d | 0.001474 |
| count_M4.5_30d | 0.001044 |
| b_value_last200 | 0.0008401 |
| count_M5.5_365d | 0.0003221 |
| mean_depth_km_30d | 0.0002565 |
| count_M4.5_7d | 0.0001977 |
| count_M5.5_30d | 0.0001846 |
## Reading the result

**Null result for the primary question.** On 2020-2025, gradient boosting with 12 seismicity-history features plus ETAS's own forecast scored the same as ETAS alone, recalibrated: -0.0003 nats per region-week, 95% CI -0.0022 to +0.0017. The features beyond ETAS add no detectable forecasting information for "M>=6 in this region next week".

**What does carry information:**

- **Mostly the region itself.** Climatology (each region's training rate) already has ROC AUC 0.727, against ETAS's 0.732. Most of what any model can say about next week is which regions are usually busy.
- **ETAS adds a little on top.** Recalibrated ETAS beats climatology by 0.0022 nats per region-week (95% CI 0.0002 to 0.0050). That is small: 9% of region-weeks have an M>=6, and a sequence is rarely the difference within one week.
- **Raw ETAS is under-confident in the middle range and slightly low overall.** Its week forecast leaves out cascades inside the week. Recalibration fixes the level; the gain of raw over climatology is not significant.
- **Boosting relies on ETAS's forecast.** Permutation importance puts the ETAS M>=6 forecast first by a factor of 7 over anything else. Time since the last M6, the region and the 365-day count follow, each worth a few thousandths of a nat.

**Secondary target (M>=7, base rate 1.2%):** boosting is worse than recalibrated ETAS (-0.0024 nats per region-week, CI -0.0047 to -0.0001). With about 200 positive training weeks it overfits. Recalibrated ETAS and climatology are indistinguishable.

**Most likely boring explanation:** the information in a catalog about next week's large quakes is mostly the current aftershock state, and ETAS already encodes it. Rearranging the same catalog into hand-made features does not reveal anything new at this scale (17 large regions, weekly windows, M>=4.5 input).

**Caveats:** one variant, no tuning, so no multiple-testing adjustment is needed. The boosting model saw ETAS features computed with ETAS parameters fitted on the same training weeks (in-sample), which, if anything, helps it on training and not on validation. Scikit-learn's histogram gradient boosting was used in place of XGBoost (same model family; XGBoost was not installable in this environment).
