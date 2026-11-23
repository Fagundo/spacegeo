# Test-period unlocks

The test span stays untouched until an experiment is pre-registered and
committed. Log every evaluation on it here.

| Date (UTC) | Experiment config | Commit | Result | Notes |
|------------|-------------------|--------|--------|-------|
| 2026-11-23 | `configs/ring_of_fire_scan.yaml` | (this PR) | Ongoing weekly | Seismicity-only anomaly monitoring uses 2026 as a live test span (models refit on 2000-2025). No space-weather inputs; see `docs/experiments/anomaly-scan.md`. |
