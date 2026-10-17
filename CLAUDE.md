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

## Architecture

Object-oriented, following SOLID. Every pipeline stage is its own package
under `src/spacegeo/`, with its interfaces (abstract base classes) in `base.py`
and concrete implementations in sibling modules.

```
src/spacegeo/
  common/            shared utilities; imports nothing else from spacegeo
  data/
    scraping/        Scraper: download raw files + provenance
    io/              DatasetReader: raw file -> validated UTC DataFrame
    preprocessing/   Preprocessor: Mc cuts, regional filters, declustering
  features/          Feature: leakage-safe covariates at forecast times
  models/            ForecastModel, EventProbabilityModel
  evaluation/        Metric, ComparativeMetric, Evaluator
  training/          TemporalSplitter, Trainer
```

**Dependencies point downward only:**
`training → evaluation → models → features → data → common`.
`data.scraping`, `data.io` and `data.preprocessing` never import each other;
they share code only through `common`.

### Where code goes

- **`common` first.** Anything two or more modules could use (time handling,
  geodesy, validation, provenance, registries, config, HTTP, fitted-state
  tracking) belongs in `common`. Before writing a helper, check `common`; if
  something similar exists, extend it there instead of writing a variant.
- **Outside `common`, behaviour lives in classes.** No public module-level
  functions in any other package. Private `_helpers` are fine.
- **One concrete class per concept**, in a module named for it
  (`data/scraping/usgs.py` → `UsgsScraper`), registered in its layer's
  registry so configs can select it by name.

### SOLID, concretely

- **Single responsibility:** a scraper only plans downloads; a reader only
  parses; a preprocessor does one transformation. Base classes own the shared
  workflow (template methods), subclasses fill in one step.
- **Open/closed:** add behaviour by adding a subclass and registering it, not
  by adding `if source == ...` branches.
- **Liskov:** every subclass must pass its layer's contract tests in
  `tests/contracts/`. A subclass that needs a weaker guarantee is a sign the
  interface is wrong; change the interface, don't special-case.
- **Interface segregation:** keep ABCs small. Log-likelihood models and
  probability models are separate interfaces; don't add methods a subset of
  implementations can't honour.
- **Dependency inversion:** constructors take abstractions (e.g. `Scraper`
  takes an `HttpClient` protocol; `Evaluator` takes `Metric`s). Concrete
  dependencies are created at the edges (configs, CLI) and injected.

## Stack

- Python 3.12+, managed with **uv** (`uv add`, `uv run`, commit `uv.lock`).
- **pandas** for frames, **pydantic** for configs.
- **ruff** (lint + format), **pyright** basic, **import-linter**, **pytest**.

## Enforcement

These run in pre-commit and in CI; a change isn't done until all pass:

```
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run lint-imports                     # layer + data-stage independence
uv run pylint --disable=all --enable=duplicate-code src   # copy-paste → move to common
uv run pytest                           # incl. tests/architecture and tests/contracts
```

- `tests/architecture/` fails if a layer lacks `base.py`, if a public
  function appears outside `common`, or if a module redefines a name that
  `common` already provides.
- `tests/contracts/` runs every concrete subclass through its interface's
  guarantees (e.g. every `Feature` is checked for future-data leakage)
  automatically. New subclasses are picked up without editing the tests.
- Ruff enforces types, docstrings, small methods (complexity ≤ 8, ≤ 6 args),
  absolute imports, no naive datetimes and no `print`.

## Code rules

- Type hints on everything public. Docstrings (Google style) state inputs,
  outputs and **units** for anything physical.
- Configs are frozen `common.config.BaseConfig` subclasses loaded from YAML;
  unknown keys are errors.
- Use `common.time.duration(...)` and `common.time.to_utc(...)`, not raw
  `pd.Timedelta`/`pd.Timestamp`, so types stay non-NaT and UTC.
- Log with `common.log.get_logger`, never `print`.
- No silent `except`. Fail loudly on malformed data.
- Notebooks live in `notebooks/` for exploration only; nothing imports from
  them, and anything worth keeping moves into `src/` with a test.

## Time and units

- Every timestamp is timezone-aware **UTC**. Naive datetimes are a bug.
- Physical columns carry their unit in the name: `bz_nT`, `speed_km_s`,
  `density_cm3`, `pdyn_nPa`, `depth_km`, `mag`, `lat_deg`, `lon_deg`.
- Longitudes are in [-180, 180). Distances are great-circle km
  (`common.geo`).
- Fill values in source data (e.g. OMNI's 999.9) become `NaN` in the reader,
  never later.

## Data

- `data/raw/` is immutable and gitignored. Only scrapers write to it, and
  they record URL, retrieval time and SHA-256 in `PROVENANCE.json`.
- `data/processed/` is gitignored and fully regenerable from raw + code.
- Never commit data files, credentials or large binaries.
- Earthquake catalog: fix a magnitude of completeness (Mc) per era and state
  it in the config. Decluster before testing for external triggering, and
  record which method and parameters were used.

## Leakage rules (non-negotiable)

- A feature at forecast time `t` may only use data with timestamp `< t`. The
  `Feature` base class enforces this; don't override `compute` unless the
  contract tests still pass.
- Splits are by time, never random, with a gap at least as long as the
  longest lookback or forecast horizon (`FeatureSet.max_lookback`).
- Stateful preprocessors and scalers are fit on the training span only.
- Aftershocks of a training-period mainshock must not appear as test positives.
- Hyperparameters are chosen on validation, never test.

## Experiments

- Every run is driven by a config in `configs/` and writes to
  `runs/<UTC-timestamp>_<slug>/`: resolved config, git commit hash, seed,
  metrics JSON, plots, and a short `NOTES.md`.
- `runs/` is gitignored; promote results worth keeping to `docs/results/`.
- Write the hypothesis and success criterion **before** running.
- Report every variant tried, not just the best, and correct for multiple
  testing when claiming significance.

## Git

- Small commits with imperative messages (`Add OMNI hourly reader`).
- Work on branches; open a PR for anything beyond trivial fixes.
- Run the `science-review` skill before merging anything that changes
  features, splits, targets or evaluation.

## Skills

- `add-component` — the general recipe for any new class in any layer.
- `add-data-source` — scraper + reader + schema for a new dataset.
- `add-feature` — a new `Feature` subclass and its rationale.
- `run-experiment` — pre-register, run, log and report an experiment.
- `science-review` — statistical-validity checklist before merging.
