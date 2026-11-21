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
