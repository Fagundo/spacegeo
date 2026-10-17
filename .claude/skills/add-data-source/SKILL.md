---
name: add-data-source
description: Use when bringing a new external dataset into spacegeo (earthquake catalog, OMNI solar wind, Kp/Dst indices, LASCO/CDAW CME catalog, etc.). Produces a Scraper, a DatasetReader with a schema, and tests.
---

# Add a data source

A source is two classes in two independent packages, plus documentation.
Follow `add-component` for the general rules.

## 1. Document it

Add a section to `docs/data-sources.md`: publisher, URL, license/terms,
coverage, cadence, file format, fill values, known gaps and revisions
(catalogs get updated), and the Mc or quality caveats.

## 2. Scraper — `src/spacegeo/data/scraping/<source>.py`

```python
@SCRAPERS.register("<source>")
class <Source>Scraper(Scraper):
    source_name = "<source>"

    def plan(self, window: TimeWindow) -> Sequence[DownloadRequest]:
        ...  # one DownloadRequest per file needed to cover the window
```

- Only implement `plan`. The base class skips current files, downloads via
  the injected `HttpClient`, and writes `PROVENANCE.json`.
- Choose file granularity (per year, per query chunk) so reruns re-fetch as
  little as possible.
- If the network blocks the source, say so and ask the user for the files;
  don't route around the block.

## 3. Reader — `src/spacegeo/data/io/<source>.py`

```python
@READERS.register("<source>")
class <Source>Reader(DatasetReader):
    schema = TableSchema(columns=(ColumnSpec("bz_nT", min_value=-500, max_value=500), ...))
    fill_values = {"bz_nT": (999.9,), ...}

    def _parse(self, path: Path) -> pd.DataFrame:
        ...  # parse one file; UTC index via common.time.assume_utc
```

- Only implement `_parse` (and declare `schema` / `fill_values`). The base
  class concatenates, replaces fill values, sorts and validates.
- Column names carry units. Longitudes via `common.geo.normalize_longitude`.
- The reader must not import the scraper (import-linter will fail); it
  receives paths.

## 4. Tests

- `tests/data/scraping/test_<source>.py`: `plan` output for a known window,
  using a fake `HttpClient`. No network.
- `tests/data/io/test_<source>.py`: a tiny real-format fixture under
  `tests/fixtures/<source>/` (a few rows, never the dataset) parses to the
  expected columns, fill values become NaN, index is UTC and sorted, and a
  bad row is rejected by the schema.

## 5. Sanity report (in the PR, not code)

Row count, time span, missing fraction per column, coverage over time.
Flag gaps and regime changes (e.g. catalog completeness jumps).
