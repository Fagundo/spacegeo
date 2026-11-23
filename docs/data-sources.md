# Data sources

One section per source: publisher, URL, license/terms, coverage, cadence,
format, fill values, known gaps and revisions. See the `add-data-source` skill.

_Planned: OMNI2 hourly, GFZ Kp, CDAW LASCO CME catalog._

## USGS ComCat (`comcat`)

- **Publisher:** U.S. Geological Survey, ANSS Comprehensive Earthquake Catalog.
- **URL:** FDSN event service, `https://earthquake.usgs.gov/fdsnws/event/1/query`
  (`format=csv`, `eventtype=earthquake`).
- **License/terms:** U.S. public domain.
- **Coverage:** global M >= 4.5 (`data/catalog/comcat_M4.5`), plus M >= 2.5 for
  Alaska-Aleutians, Cascadia and California-Baja, where US networks record small
  quakes (`data/catalog/comcat_M2.5_<region>`, bounding-box queries). The list
  of archives is `configs/catalogs.yaml`.
- **Cadence:** near-real-time; events are revised for days to weeks (magnitude,
  location, status `automatic` -> `reviewed`, occasional deletions).
- **Format:** CSV, one row per event. Read columns: `time` (ISO-8601 UTC),
  `latitude`, `longitude`, `depth` (km), `mag`, `magType`, `id`.
  Output names: `lat_deg`, `lon_deg`, `depth_km`, `mag`, `mag_type`, `event_id`.
- **Fill values:** none; missing magnitudes arrive empty and become NaN
  (dropped by `MagnitudeCut`).
- **Chunking:** one query per calendar year (service limit 20,000 events per
  query; global M>=4.5 is ~7-9k/year). The trailing partial chunk is named by
  its end date so recent revisions are re-fetched.
- **Caveats:** `mag` mixes magnitude types (Mw, mb, ...). Global completeness
  near M4.5 holds from the 2000s on but is worse in remote oceanic segments.
  The newest few days are incomplete and preliminary: small events get added
  late, so a "deficit" in the last 1-2 days can be a reporting lag.

