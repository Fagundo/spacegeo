---
name: run-experiment
description: Use when running any spacegeo model or statistical test (ETAS baseline, ETAS + space-weather covariates, binary M>=X classifiers, graph models). Pre-registers the hypothesis, runs from config, logs everything and reports honestly.
---

# Run an experiment

Goal: a reproducible run whose result means what it claims, positive or null.

## 1. Pre-register (before any code runs)

Create `configs/<slug>.yaml` and at its top, as comments or a `prereg:` block,
write:

- **Hypothesis:** one sentence.
- **Comparison:** the exact baseline (normally ETAS fitted on the same
  training span and declustering choices).
- **Metric and success criterion:** e.g. "information gain over ETAS > 0
  with 95% bootstrap CI excluding 0 on the validation span."
- **Data choices:** catalog, Mc, region definition, magnitude threshold,
  declustering method + parameters, train/val/test spans and gap.
- **Number of variants** planned in this family of experiments.

Commit the config before running. Do not edit the pre-registration after
seeing results; add a new config instead.

## 2. Run

- Launch via the package CLI (`uv run spacegeo run configs/<slug>.yaml`) so
  every run goes through the same code path.
- Output to `runs/<UTC-timestamp>_<slug>/` containing:
  - `config.resolved.yaml`
  - `git.txt` (commit hash + dirty flag; refuse to run on a dirty tree
    unless `--allow-dirty` is passed and noted)
  - `seed.txt`
  - `metrics.json`
  - plots (reliability/calibration, information gain over time, residuals)
  - `NOTES.md`
- Fix all random seeds. Evaluate on **validation** only. The test span
  stays locked (see CLAUDE.md).

## 3. Report

Fill `NOTES.md` and summarize to the user:

- Result vs the pre-registered criterion: met / not met. Plain words.
- Effect size with uncertainty (bootstrap or block-bootstrap by time).
- Base rate of the target, and baseline performance alongside the model.
- How many variants have now been tried in this family; adjust significance
  accordingly (Bonferroni or FDR) and say so.
- Anything surprising, and the most likely boring explanation for it.

Never describe a result as "promising" or "suggestive" when it misses the
pre-registered criterion. A null is reported as a null.

## 4. Promote

If the result is worth keeping, copy metrics, plots and NOTES into
`docs/results/<date>_<slug>/` and commit.
