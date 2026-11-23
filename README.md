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

```bash
uv run python scripts/scan_anomalies.py                     # week ending today 00:00 UTC
uv run python scripts/scan_anomalies.py --end 2026-11-23T00:00Z
```

For each region in `configs/ring_of_fire_scan.yaml`, compares the last week's
M>=4.5 count with that region's 2000-2019 history, two ways:

- `activity`: raw catalog vs. a negative binomial fitted to weekly counts
  (allows for typical aftershock clustering).
- `mainshocks`: Gardner-Knopoff declustered catalog vs. a Poisson rate.

P-values (excess and deficit) are Benjamini-Hochberg corrected across all
regions; `flag` marks q <= 0.05. Output goes to `runs/<UTC>_anomaly-scan/`.
This is monitoring, not a test of the space-weather hypothesis.

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
