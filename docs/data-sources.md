# Data sources

One section per source: publisher, URL, license/terms, coverage, cadence,
format, fill values, known gaps and revisions. See the `add-data-source` skill.

_Planned: CDAW LASCO CME catalog._

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


## NASA OMNI2 hourly (`omni2`)

- **Publisher:** NASA/GSFC Space Physics Data Facility (SPDF), OMNIWeb.
- **URL:** `https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2_YYYY.dat`;
  format description in `omni2.text` in the same directory.
- **License/terms:** NASA open data; cite OMNIWeb (King & Papitashvili 2005,
  doi:10.1029/2004JA010649) and the index providers (WDC Kyoto for Dst/AE,
  GFZ for Kp, SILSO for SN, NRCan/DRAO for F10.7).
- **Coverage:** 1963 on, hourly. Archive: `data/space_weather/omni2/`, 2000 on.
- **Cadence:** files are re-issued every few weeks to months. IMF and plasma
  lag real time by weeks; Dst and AE arrive as real-time/provisional values
  first and become final years later. The last two years are always
  re-downloaded.
- **Format:** ASCII, one row per hour, 55 whitespace-separated words
  (year, day of year, hour, then values). Timestamps are hour starts (UTC);
  values are hourly averages time-shifted to the bow-shock nose.
  Kept words and output columns: 9 `b_mag_nT`, 13 `bx_gse_nT`,
  16 `by_gsm_nT`, 17 `bz_gsm_nT`, 22 `sigma_bz_nT` (within-hour std of Bz),
  23 `temperature_K`, 24 `density_cm3`, 25 `speed_km_s`, 29 `pdyn_nPa`,
  36 `ey_mV_m`, 39 `kp` (OMNI's 10*Kp code converted to thirds),
  40 `sunspot_number`, 41 `dst_nT`, 42 `ae_nT`, 50 `ap`, 51 `f107_sfu`,
  53 `al_nT`, 54 `au_nT`.
- **Fill values (become NaN in the reader):** 999.9 (field, density,
  sigmas, F10.7), 9999999. (temperature), 9999. (speed, AE), 99.99
  (pressure), 999.99 (E field), 99 (Kp code), 999 (SN, ap), 99999 (Dst,
  AL, AU).
- **Known gaps:** solar-wind coverage is ~90%+ hourly since ACE/Wind (late
  1990s) but has multi-hour gaps; AE/AL/AU have long gaps (e.g. parts of
  the 2010s) and are often provisional only. F10.7 and SN are daily values
  repeated over 24 rows. Never forward-fill across gaps.

## GFZ Potsdam Kp (`gfz_kp`)

- **Publisher:** GFZ German Research Centre for Geosciences (Matzka et al.
  2021, doi:10.1029/2020SW002641).
- **URL:** `https://kp.gfz.de/app/files/Kp_ap_Ap_SN_F107_since_1932.txt`
  (one file, rewritten daily).
- **License/terms:** CC BY 4.0; cite the GFZ Kp data publication.
- **Coverage:** 1932 on. Archive: `data/space_weather/gfz_kp/`, 2000 on,
  one row per 3-hour interval (00, 03, ..., 21 UTC; index = interval start).
- **Format:** `#`-comment header, then one row per day:
  `YYYY MM DD days days_m Bsr dB Kp1..Kp8 ap1..ap8 Ap SN F10.7obs F10.7adj D`.
  Output columns: `kp` (thirds, 0-9), `ap` (units of 2 nT), `kp_definitive`
  (`D >= 1`). Daily SN and F10.7 are taken from OMNI2 instead.
- **Fill values:** -1 (Kp, ap, SN, F10.7) become NaN.
- **Revisions:** recent days are nowcast values (`D = 0`) and become definitive
  after about a month, so recent years are always re-downloaded.

## INTERMAGNET observatories, hourly dB/dt (`intermagnet`)

- **Publisher:** INTERMAGNET (International Real-time Magnetic Observatory
  Network), served by the BGS Edinburgh Geomagnetic Information Node.
- **URL:** HAPI 3.1 service `https://imag-data.bgs.ac.uk/GIN_V1/hapi`;
  dataset `<code>/best-avail/PT1M/xyzf` (definitive where available, else
  quasi-definitive/reported), parameter `Field_Vector` (X, Y, Z in nT).
  `info?dataset=...` gives coordinates (`x_latitude`, `x_longitude` 0-360),
  `startDate`, `stopDate`, fill value and `maxRequestDuration` (P366D).
- **License/terms:** INTERMAGNET conditions of use: cite INTERMAGNET and the
  individual observatory institutes, e.g. "The results presented in this
  paper rely on data collected at magnetic observatories. We thank the
  national institutes that support them and INTERMAGNET for promoting high
  standards of magnetic observatory practice (www.intermagnet.org)."
- **Stations:** candidates in `configs/magnetometers.yaml`; metadata in
  `data/space_weather/intermagnet/<CODE>/station.json`.
- **Cadence:** 1-minute samples stamped at minute start. Refreshed monthly
  (`magnetometers` workflow); the most recent year is always re-downloaded.
- **Stored product (not the minute data):** per station and hour (stamped at
  the hour start), from minute pairs whose two samples both start in that
  hour: `dbh_dt_max_nT_min` and `dbh_dt_mean_nT_min`, the max and mean of
  sqrt(dX^2 + dY^2) per minute (nT/min), and `n_pairs` (0-59). Hours with
  fewer than 30 valid pairs have NaN statistics. Raw minute files are
  deleted on the runner after reduction (about 20 MB per station-year).
- **Fill values:** 99999.0 in X/Y/Z becomes NaN in the reader. An empty HAPI
  response (no data for the request) is an empty frame.
- **Known issues:** reported (non-definitive) data can contain spikes, which
  inflate hourly maxima; the mean is less sensitive. Observatory coverage
  starts and stops (some stations close or join after 2000).
