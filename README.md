# spacegeo

Does space weather add any predictive information to earthquake forecasts
beyond what seismicity itself provides? This project tests that question
with an ETAS baseline, leakage-safe space-weather covariates, and
pre-registered evaluation on a locked test period.

## Setup

```bash
uv sync --all-groups
uv run pre-commit install
uv run pytest
```

## Weekly Ring of Fire anomaly scan

Latest results: [`results/anomaly/test/latest.md`](results/anomaly/test/latest.md)
(updated every Monday by the `Weekly anomaly scan` workflow).

For each region in `configs/ring_of_fire_scan.yaml`, each week's M>=4.5 count
is compared with that region's own history, two ways:

- `activity`: raw catalog vs. the distribution of that region's past weekly
  counts (aftershock bursts included as they actually occurred).
- `mainshocks`: causal Gardner-Knopoff declustered catalog vs. a Poisson rate.

Split: train 2000-2019, validation 2020-2025 (calibration check), test 2026
onward (models refit on 2000-2025). Validation also reports log scores of
candidate models with bootstrap intervals, a PIT calibration plot and an
injection-based detection power curve:
[`results/anomaly/validation/README.md`](results/anomaly/validation/README.md). Pre-registration:
[`docs/experiments/anomaly-scan.md`](docs/experiments/anomaly-scan.md).

Run locally:

```bash
uv run python scripts/update_catalog.py          # refresh data/catalog/
uv run python scripts/scan_anomalies.py validate # once
uv run python scripts/scan_anomalies.py predict
```

## Layout

```
src/spacegeo/
  common/            shared utilities (time, geo, validation, provenance, ...)
  data/scraping/     download raw files
  data/io/           parse into validated UTC DataFrames
  data/preprocessing/  completeness cuts, declustering, ...
  features/          leakage-safe covariates
  models/            ETAS and covariate models
  evaluation/        information gain and other metrics
  training/          temporal splits and fitting
```

Conventions and enforcement are in [CLAUDE.md](CLAUDE.md).
