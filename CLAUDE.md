# spacegeo

Tests whether space weather (solar wind, geomagnetic activity, CMEs) carries any
predictive information about significant earthquakes beyond what seismicity
already tells us. A clean null result is a valid, publishable outcome; the job
is to get the answer right, not to find a signal.

## Research contract

- **Primary question:** does adding space-weather covariates to an ETAS
  baseline improve out-of-sample earthquake forecasts?
- **Primary metric:** information gain (log-likelihood per event) of
  ETAS + space weather over ETAS alone, on a held-out time period.
- **Secondary target:** binary "M ≥ X within region R within D days after an
  observation window", always reported against the base rate and the ETAS
  baseline, never against chance alone.
- **Locked test period:** the final years of the catalog are reserved. Nothing
  touches them until a hypothesis, config and metric have been written down
  and committed. Record each unlock in `docs/test-unlocks.md`.

## Stack

- Python 3.12, managed with **uv** (`uv add`, `uv run`, commit `uv.lock`).
- Package lives in `src/spacegeo/`; tests in `tests/` mirror its layout.
- **pandas** is the default dataframe library.
- **ruff** for lint and format; **pyright** in basic mode.
- **pytest** for tests.
- Before calling work done: `uv run ruff format`, `uv run ruff check`,
  `uv run pyright`, `uv run pytest` must all pass.

## Code rules

- Type hints on every public function and dataclass. Pyright basic must pass;
  untyped third-party libs are fine.
- Prefer small, pure functions: data in, data out, no hidden I/O or globals.
  I/O lives at the edges (`io/`, `cli/`), transforms in the middle.
- Docstrings state inputs, outputs and **units** for anything physical.
- Configuration is a typed dataclass or pydantic model loaded from YAML, not
  loose dicts or constants buried in code.
- No notebook-only logic. Notebooks live in `notebooks/` for exploration;
  anything worth keeping moves into `src/` with a test. Nothing imports from
  notebooks.
- No silent `except`. Fail loudly on malformed data.

## Time and units

- Every timestamp is timezone-aware **UTC** (`pd.Timestamp(..., tz="UTC")`).
  Naive datetimes are a bug.
- Physical columns carry their unit in the name: `bz_nT`, `speed_km_s`,
  `density_cm3`, `pdyn_nPa`, `depth_km`, `mag`, `lat_deg`, `lon_deg`.
- Longitudes are in [-180, 180). Distances use great-circle (haversine) in km.
- Fill values in source data (e.g. OMNI's 999.9, 9999.) become `NaN` at load
  time, never later.

## Data

- `data/raw/` is immutable and gitignored. Only download scripts write to it.
- Every source has a download module in `src/spacegeo/io/` that records URL,
  retrieval time, and SHA-256 in `data/raw/<source>/PROVENANCE.json`.
- `data/processed/` is gitignored and fully regenerable from raw + code.
- Never commit data files, credentials or large binaries.
- Earthquake catalog: fix a magnitude of completeness (Mc) per era and state
  it in the config. Decluster before testing for external triggering, and
  record which method and parameters were used.

## Leakage rules (non-negotiable)

- A feature at forecast time `t` may only use data with timestamp `< t`.
  Every feature function ships with a test proving it (see `add-feature`).
- Splits are by time, never random, with a gap at least as long as the
  longest lookback or forecast horizon.
- Normalization and any fitted preprocessing are fit on the training span only.
- Aftershocks of a training-period mainshock must not appear as test positives.
- Hyperparameters are chosen on validation, never test.

## Experiments

- Every run is driven by a config in `configs/` and writes to
  `runs/<UTC-timestamp>_<slug>/`: resolved config, git commit hash, seed,
  metrics JSON, plots, and a short `NOTES.md`.
- `runs/` is gitignored; promote results worth keeping to `docs/results/`.
- Write the hypothesis and success criterion **before** running (see
  `run-experiment`).
- Report every variant tried, not just the best. Count comparisons and correct
  for multiple testing when claiming significance.

## Git

- Small commits with imperative messages (`Add OMNI hourly loader`).
- Work on branches; open a PR for anything beyond trivial fixes.
- Run the `science-review` skill before merging anything that changes
  features, splits, targets or evaluation.

## Skills

- `add-data-source` — bring in a new dataset with provenance and validation.
- `add-feature` — add a model feature with a mandatory no-leakage test.
- `run-experiment` — pre-register, run, log and report an experiment.
- `science-review` — checklist for statistical validity before merging.
