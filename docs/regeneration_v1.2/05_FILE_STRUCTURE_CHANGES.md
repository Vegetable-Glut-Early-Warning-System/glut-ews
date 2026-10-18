# File structure changes (v1.1 → v1.2)

`+` added · `~` changed · `−` removed. Everything else is unchanged.

```
glut-ews/
├── data/
│   ├── glut_ews.duckdb                         ~ brand-new database built by scripts/build_db.py (DVC: new version)
│   ├── config/
│   │   └── crop_district_footprint.csv        + crop–district footprint with evidence (Git)
│   ├── reference/                              + curated reference tables, CSV (Git): dim_*, bridge, cost, CCPI,
│   │                                             national supply, national planting targets, model parameters
│   ├── raw/
│   │   ├── source_manifest.csv                 ~ two new sources with SHA-256
│   │   ├── extracts/                           + source extracts as published, Parquet (DVC) — build input
│   │   └── sources/                            ~ (DVC) + wfp_food_prices_lk.csv, dcs_weekly_retail_prices.csv
│   └── outputs/                                  published module outputs only (v1+); re-applied by every build
├── parquet/                                    ~ re-exported by every build/rebuild
├── sql/
│   ├── schema.sql                              + full table definitions (types, primary keys)
│   └── views.sql                                 (unchanged)
├── scripts/
│   ├── build_db.py                             + builds the database from scratch
│   ├── rebuild_db.py                           ~ published outputs + views only; core-update path removed; new checks
│   └── validate_dataset.py                     + validation summary + data dictionary
├── src/glut_ews/
│   ├── build/generator.py                      + generation of modelled tables and v0 outputs (seed 20261018)
│   └── common/schema.py · __init__.py · publish.py   ~ label validation removed; dim_crop_district key; "v0" reserved
├── tests/
│   ├── test_build.py                           + fresh build reproduces the committed database
│   ├── test_dataset_realism.py                 + 10 audit rules
│   └── test_rebuild.py                         ~ v0 label; footprint and unknown-table rejections
├── notebooks/c1…c4_01_eda.ipynb                ~ footprint cell replaces the label query
├── docs/
│   ├── regeneration_v1.2/                      + audit, findings, checklist, DVC walkthrough, this file
│   ├── data_sources_and_methods.md             + where each table's data comes from; observed-only subsets
│   ├── validation_summary.md · v0_outputs_report.md · generation_report.json · crop_district_footprint.csv   +
│   ├── DATASET_README.md · DATASHEET.md        ~ updated
│   ├── data_dictionary.csv · known_issues.csv · model_parameters.csv · table_inventory.csv · build_manifest.json   ~ regenerated
│   └── TEAM_GUIDE.md · placeholder_realism_report.md · placeholder_realism_metrics.json   − removed
├── README.md                                   ~ build from scratch (10.3–10.4), footprint, no label section
├── pyproject.toml                              ~ ruff per-file ignores
└── .gitignore                                  ~ raw extracts, build temp file, .vscode/
```

## Database objects

| Object | Change |
|---|---|
| Whole database | Built new from `sql/schema.sql`; no migration history; 22 primary keys enforced; dates typed `DATE` |
| `core.dim_crop_district` | + 29 rows (24 core, 5 proposed) |
| `raw.wfp_market_prices`, `raw.dcs_weekly_retail_prices` | + new sources as published |
| 11 core tables | no `provenance` column |
| `core.national_supply_season`, `core.cost_season` | no `note` column |
| `core.supply_season`, `core.planting_target_season` | 402 rows (footprint only) |
| `core.market_prices_weekly` | 19,656 rows (54 traded combinations), recalibrated, no NULLs |
| `core.market_arrivals_weekly` | 14,104 rows (39 supplied combinations) |
| `core.weather_daily` | modelled days after 2024-06-08 regenerated |
| `outputs.*` | v0 on the footprint; C2 `top_drivers`, C3 `top_reasons`; `c4_advisory` defined (empty until C4 publishes) |
| `outputs_history` | schema present; tables created on the first replacement of a version |
| `views.*` | definitions unchanged; component 2–4: 402 rows, component 1: 14,104 rows |

## How the Parquet files are updated

`parquet/` is never edited. Every successful `build_db.py` or `rebuild_db.py` re-exports each table and component view to `parquet/<schema>/<table>.parquet` and deletes files for tables that no longer exist; then `dvc add parquet` records the version.

| Folder | Files in v1.2 |
|---|---|
| `parquet/raw/` | 12 (+ `wfp_market_prices`, `dcs_weekly_retail_prices`) |
| `parquet/core/` | 18 (+ `dim_crop_district`) |
| `parquet/outputs/` | 5 (+ empty `c4_advisory`) |
| `parquet/views/` | 4 |
