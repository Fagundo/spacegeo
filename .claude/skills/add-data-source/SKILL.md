---
name: add-data-source
description: Use when bringing a new external dataset into spacegeo (earthquake catalog, OMNI solar wind, Kp/Dst indices, LASCO/CDAW CME catalog, etc.) so it arrives with provenance, a schema and tests.
---

# Add a data source

Goal: a new dataset can be downloaded reproducibly, loaded into a clean,
UTC-indexed pandas DataFrame with unit-labelled columns, and trusted.

## Steps

1. **Document the source first.** Add a section to `docs/data-sources.md`:
   name, publisher, URL, license or terms, temporal coverage, cadence,
   known gaps, fill values, and any versioning (catalogs get revised).

2. **Download module** at `src/spacegeo/io/<source>.py`:
   - `download(dest: Path, start: date, end: date) -> Path` writes only into
     `data/raw/<source>/`.
   - Records URL(s), UTC retrieval time, and SHA-256 of each file in
     `data/raw/<source>/PROVENANCE.json`.
   - Idempotent: skips files whose checksum already matches.
   - If the network blocks the source, say so and ask the user to provide
     the file; do not route around the block.

3. **Loader** in the same module:
   - `load(path: Path) -> pd.DataFrame`, pure: reads raw, returns clean.
   - Index is a tz-aware UTC `DatetimeIndex`, sorted, duplicates resolved
     explicitly (document the rule).
   - Fill values → `NaN` here, and only here.
   - Column names carry units (`bz_nT`, `speed_km_s`, `mag`, `depth_km`).
   - Longitudes normalized to [-180, 180).

4. **Schema** with pandera or an explicit `validate(df)` function: dtypes,
   ranges (e.g. `0 <= depth_km <= 800`, `-90 <= lat_deg <= 90`), monotonic
   index, required columns. Call it at the end of `load`.

5. **Tests** in `tests/io/test_<source>.py`, using a tiny fixture file
   committed under `tests/fixtures/<source>/` (a few real-format rows, never
   the full dataset):
   - parses the fixture into the expected columns and dtypes;
   - fill values become NaN;
   - timestamps are UTC and sorted;
   - schema rejects an obviously bad row.

6. **Quick sanity report** (not committed as code; paste into the PR): row
   count, time span, fraction missing per column, and a plot of coverage
   over time. Flag gaps or regime changes (e.g. catalog completeness jumps).

7. Run `uv run ruff format && uv run ruff check && uv run pyright && uv run pytest`.

## Done when

- `docs/data-sources.md` updated.
- Download + loader + schema + tests merged, all checks green.
- No data files committed.
