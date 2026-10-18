# Dataset audit report (v1.1 → v1.2)

Audit of every `core` and `outputs` table in dataset v1.1, carried out **before** regeneration. Each figure was measured on the v1.1 database; each fix is enforced by a check in `scripts/rebuild_db.py` and/or `tests/test_dataset_realism.py`, so it cannot silently come back.

Severity: **Critical** = invalidates analyses · **High** = biases results · **Medium** = unrealistic pattern detectable by a reviewer · **Low** = cosmetic or documentation.

| # | Issue | Where | Measured in v1.1 | Severity | Fix applied in v1.2 | Enforced by |
|---|---|---|---|---|---|---|
| A1 | Every crop present in every district | `core.supply_season` | 1,750 rows = exactly 25 × 5 × 14 | Critical | New `core.dim_crop_district` (29 pairs: 24 core + 5 proposed); rows only for footprint pairs → 402 rows | rebuild integrity check; `test_supply_only_in_footprint` |
| A2 | Zero placeholder rows and implausibly tiny "commercial" extents | `core.supply_season` | 150 rows with extent 0; 433 rows < 10 ha | High | No rows where a crop isn't grown; footprint districts carry their DOA-reported share (minimum 8 ha) | `test_no_zero_or_placeholder_rows` |
| A3 | Production without extent | `core.supply_season` | 1 row (extent 0, production > 0) | High | Production = extent × yield for every row | `test_yields_in_agronomic_range_and_consistent` |
| A4 | Targets for districts that don't grow the crop | `core.planting_target_season` | 1,750 rows (full grid) | High | Footprint rows only (402); 163 targets taken directly from DOA Crop Forecast | rebuild integrity check |
| A5 | District outputs for non-producing districts | `outputs.c2_pressure_score`, `c3_*` | 1,750 rows each | High | v0 outputs regenerated on the footprint (402 rows each) | rebuild integrity check |
| A6 | District production forced to sum to national totals | `core.supply_season` | District yields were whatever the rescaling produced | Medium | District yield = national seasonal yield × DOA district yield factor × weather × variation, within crop ranges; not rescaled (footprint ≈ 53–68% of national extent; KI-17) | `test_yields_in_agronomic_range_and_consistent` |
| A7 | Identical national yield in all seasons | `core.national_supply_season` (winged bean) | 10.30 t/ha in 14 of 14 seasons | Medium | DOA expected-production yields for 3 seasons; modelled variation for 11 | `test_yield_not_uniform` |
| A8 | Centre prices = Colombo × a fixed invented factor | `core.market_prices_weekly` | 11 centres at constant factors 0.85–1.03; ratio variation 7.5% (noise only) | High | Ratios from WFP market prices (observed months, time-varying); producing-area wholesale anchored on WFP Dambulla/Pettah (0.837); variation calibrated to WFP (CV 8–15%) | `test_centre_prices_not_constant_multiples` |
| A9 | Price series for crops not traded at a centre | `core.market_prices_weekly` | 60 of 60 centre–crop combinations | Medium | 54 combinations; removed Bandarawela–winged bean, Keppetipola–cucumber/green chilli/winged bean, Norochcholai–tomato/winged bean | `test_not_a_full_grid` |
| A10 | Missing Colombo price weeks | `core.market_prices_weekly` | 1,680 NULL rows (28 weeks × 60) | Medium | Filled from DCS weekly retail (level-adjusted, r = 0.96–0.99): ~17–21 weeks per crop; remaining short gaps interpolated; 0 NULLs | rebuild integrity check |
| A11 | Arrivals at centres with no supplying district; zero-arrival rows | `core.market_arrivals_weekly` | 21,840 rows (full grid), 405 zero rows | Medium | Arrivals only where footprint districts supply the centre: 39 combinations, 14,104 rows, 0 zeros | `test_no_zero_or_placeholder_rows`; arrivals ⊂ prices check |
| A12 | Modelled weather copied verbatim from past years | `core.weather_daily` (from 2024-06-09) | 62% of rows identical to a past year | Medium | Day-level perturbation of analog days: 2.9% coincidental matches; dry-day share kept (17.7% vs 17.9%) | — (measured) |
| A13 | Row counts no real dataset would have | supply, targets, prices, arrivals, outputs | 25 × 5 × 14, 12 × 5 × 364 everywhere | Medium | Counts follow the footprint and market coverage (402 / 19,656 / 14,104) | `test_not_a_full_grid` |
| A14 | Row-level labels marking data as synthetic | 11 core tables (`provenance`), 2 tables (`note`), outputs (`placeholder_v0`) | 13 columns + version label | — (requested) | Columns not defined in `sql/schema.sql` (brand-new database); version renamed `v0`; origin documented at table level (`docs/data_sources_and_methods.md`) | `test_no_row_level_label_columns` |
| A15 | New data: WFP "Chili" is dried chilli | `raw.wfp_market_prices` | r = 0.99 with DCS dried chillies, 0.20 with HARTI green chilli | High (if used) | Excluded from green chilli calibration (KI-16) | — |
| A16 | Name variants in source tables | `raw.cf_district_tables` | "Moneragala", "Nuwaraeliya", "Pol onnaruwa IP", "Hasal aka IP" … | Low | Canonicalised in core (unchanged); 0 orphan names | `test_names_link_to_reference_tables` |
| A17 | Wholesale above retail / implausible prices / dates out of range | `core.market_prices_weekly` | 0 / 0 / 0 (no violation) | — | Constraints now enforced (retail ≥ 1.10 × wholesale at modelled centres) | rebuild integrity check; `test_prices_plausible` |
| A18 | Farm-gate below unit cost | `core.cost_season` | 4 seasons | Low (real) | No change: DOA surveys report genuine losses (e.g. 2018/19 Maha pumpkin) | — |

## Not changed, and why

- **`raw.*`** — kept exactly as published (the audit trail).
- **`core.cost_season`, `core.macro_monthly`, `core.bridge_district_centre`, dimension tables** — no unrealistic pattern beyond the dropped labels; values unchanged.
- **`core.national_supply_season`** — published DCS/AgStat values unchanged except winged bean yield (A7).

## Downstream impact (tell module owners)

| Change | Who is affected |
|---|---|
| `provenance` and `note` columns no longer exist | Anyone querying them (notebooks updated) |
| District panel: 1,750 → 402 rows; districts per crop 25 → 5–7 | C2, C3, C4 (no fixed-size pivots or assumptions of all 25 districts) |
| `views.component1_dataset`: 21,840 → 14,104 rows (only centre–crop pairs with arrivals) | C1 (full price coverage remains in `core.market_prices_weekly`, 54 pairs) |
| `outputs.c1_glut_season`: 840 → 756 rows | C1, C2, C3 |
| Version label `placeholder_v0` → `v0`; `publish_output` refuses `v0` | All modules |
| New table `core.dim_crop_district` | C4 (suitability), anyone filtering districts |
