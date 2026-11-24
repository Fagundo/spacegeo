# Features

| Name | Inputs | Window | Physical rationale |
|------|--------|--------|--------------------|
| `newell_coupling` | OMNI2 `speed_km_s`, `by_gsm_nT`, `bz_gsm_nT` (hourly) | log EMA over τ = 1, 4, 16 d (truncated at 4τ) minus log EMA over 365 d; hours ending before t | Newell coupling v^(4/3) B_T^(2/3) sin^(8/3)(θ/2) measures energy entering the magnetosphere; storms, ring current and induced ground currents follow it. Mechanism E of `space-weather-etas`. |
| `bz_sigma` | OMNI2 `sigma_bz_nT` (hourly) | as above | Within-hour IMF Bz fluctuation: turbulent driving gives larger dB/dt and induced currents than steady driving. Mechanism V. |
| `dynamic_pressure` | OMNI2 `pdyn_nPa` (hourly) | as above | Solar-wind pressure compresses the magnetosphere (sudden impulses); surface pressure change ~1e-6 Pa. Mechanism C. |
