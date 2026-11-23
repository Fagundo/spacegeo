# Data sources

One section per source: publisher, URL, license/terms, coverage, cadence,
format, fill values, known gaps and revisions. See the `add-data-source` skill.

_Planned: OMNI2 hourly, GFZ Kp, CDAW LASCO CME catalog._

## USGS ComCat (`comcat`)

- **Publisher:** U.S. Geological Survey, ANSS Comprehensive Earthquake Catalog.
- **URL:** FDSN event service, `https://earthquake.usgs.gov/fdsnws/event/1/query`
  (`format=csv`, `eventtype=earthquake`).
- **License/terms:** U.S. public domain.
- **Coverage:** global; this project downloads M >= 2.5 and cuts each region at
  its own Mc. Small events are dense only where US networks contribute
  (Alaska, Cascadia, California); elsewhere ComCat is roughly complete from M4-4.5.
- **Cadence:** near-real-time; events are revised for days to weeks (magnitude,
  location, status `automatic` -> `reviewed`, occasional deletions).
- **Format:** CSV, one row per event. Read columns: `time` (ISO-8601 UTC),
  `latitude`, `longitude`, `depth` (km), `mag`, `magType`, `id`.
  Output names: `lat_deg`, `lon_deg`, `depth_km`, `mag`, `mag_type`, `event_id`.
- **Fill values:** none; missing magnitudes arrive empty and become NaN
  (dropped by the magnitude cuts).
- **Chunking:** configurable; monthly at M2.5 (service limit 20,000 events per
  query; global M>=4.5 is ~7-9k/year, M>=2.5 several times that). A file that
  reaches the limit is rejected as probably truncated. The trailing partial
  chunk is named by its end date so recent revisions are re-fetched.
- **Caveats:** `mag` mixes magnitude types (Mw, mb, ...). Global completeness
  near M4.5 holds from the 2000s on but is worse in remote oceanic segments.
  The newest few days are incomplete and preliminary: small events get added
  late, so a "deficit" in the last 1-2 days can be a reporting lag.

