# Removal of row-level data labels — checklist

## What was removed

| Item | Where | Action |
|---|---|---|
| `provenance` column | 11 core tables: `bridge_district_centre`, `cost_season`, `harvest_weekly_national`, `macro_monthly`, `market_arrivals_weekly`, `market_prices_weekly`, `model_parameters`, `national_supply_season`, `planting_target_season`, `supply_season`, `weather_daily` | Not defined in `sql/schema.sql`; the database is built new without it |
| `note` column (free text stating "Synthetic …", "Estimate …", "Derived …" per row) | `core.national_supply_season`, `core.cost_season` | Not defined in `sql/schema.sql` — **additional label column found during the audit** |
| Version value `placeholder_v0` | `outputs.*.source_version` | Generated as `v0`. The **column** stays: the publish → rebuild workflow and the output contracts depend on it to know which version is active. |
| "(provenance=…)" wording | `core.known_issues.core_handling` | Rewritten by the generator |

Not a label, left in place: `outputs_history.archived_at` (version history), `core.dim_crop_district.status` (core / proposed footprint — a research decision, not a data-origin label).

## Where the information lives now

The origin of every table and of each part of a table is documented in **`docs/data_sources_and_methods.md`** (published / derived / modelled, with counts and SQL for observed-only subsets), and methods in `docs/DATASHEET.md`. This keeps the methodology and the observed-subset evaluation possible without a per-row column.

## File-by-file checklist

| File / location | Change | Status |
|---|---|---|
| Database | Built brand-new from `sql/schema.sql`: no `provenance` or `note` columns, `source_version` = 'v0' | ✅ |
| `sql/schema.sql` | **New**: full table definitions (types, primary keys) — the columns simply aren't there | ✅ |
| `scripts/build_db.py` | **New**: builds the database from scratch | ✅ |
| Migrations | **None** — no migration files, no `meta` schema | ✅ |
| `src/glut_ews/common/schema.py` | `PROVENANCE` constant and provenance validation removed; `dim_crop_district` key added | ✅ |
| `src/glut_ews/common/__init__.py` | `PROVENANCE` export removed | ✅ |
| `src/glut_ews/common/publish.py` | "placeholder_v0 reserved" → "v0 reserved" | ✅ |
| `src/glut_ews/common/contracts.py` | No reference (unchanged) | ✅ checked |
| `scripts/rebuild_db.py` | Core-update path and provenance checks removed; footprint, non-positive and wholesale ≤ retail checks added | ✅ |
| `src/glut_ews/build/generator.py` | **New**; writes no label columns | ✅ |
| `scripts/validate_dataset.py` | **New**; checks that no label column exists | ✅ |
| `sql/views.sql` | No reference (unchanged) | ✅ checked |
| `tests/test_rebuild.py` | `placeholder_v0` → `v0`; core-update test no longer uses `note`; row counts no longer hard-coded | ✅ |
| `tests/test_dataset_realism.py` | **New**; `test_no_row_level_label_columns` guards against reintroduction | ✅ |
| `tests/test_build.py` | **New**; a fresh build must reproduce the committed database | ✅ |
| `notebooks/c1_01_eda.ipynb` … `c4_01_eda.ipynb` | Provenance query cell replaced by a footprint query | ✅ |
| `README.md` | Provenance section replaced by "Where the data comes from"; rules and update paths reworded | ✅ |
| `docs/DATASET_README.md` | Rewritten (no label vocabulary) | ✅ |
| `docs/DATASHEET.md` | Per-row label sentence replaced by a pointer to the methods document; methods updated | ✅ |
| `docs/data_dictionary.csv` | Regenerated from the database | ✅ |
| `docs/known_issues.csv`, `docs/model_parameters.csv` | Re-exported from the database | ✅ |
| `docs/placeholder_realism_report.md`, `docs/placeholder_realism_metrics.json` | Deleted; replaced by `docs/v0_outputs_report.md` | ✅ |
| `docs/TEAM_GUIDE.md` | Deleted (superseded by README) | ✅ |
| `parquet/` | Re-exported by the rebuild (no label columns) | ✅ |
| API / DTOs / ORM models | None exist yet (`api/` is empty) — when built, read from the database schema | n/a |

Verification: `grep -rn "provenance" src scripts tests notebooks sql/views.sql` returns nothing; `tests/test_dataset_realism.py::test_no_row_level_label_columns` passes.

## Schema definition

There is no migration SQL: the database is created new by `scripts/build_db.py` from `sql/schema.sql`, which defines every core and outputs table without label columns. For example:

```sql
CREATE TABLE core.supply_season (
    season VARCHAR, district VARCHAR, crop VARCHAR, extent_ha DOUBLE NOT NULL, production_t DOUBLE NOT NULL,
    yield_t_ha DOUBLE NOT NULL, PRIMARY KEY (season, district, crop));
CREATE TABLE core.national_supply_season (
    season VARCHAR, crop VARCHAR, extent_ha DOUBLE, production_t DOUBLE, yield_t_ha DOUBLE, PRIMARY KEY (season, crop));
CREATE TABLE core.dim_crop_district (
    crop VARCHAR, district VARCHAR, status VARCHAR NOT NULL, justification VARCHAR, source VARCHAR,
    PRIMARY KEY (crop, district));
```

Going back to v1.1 = check out the `dataset-v1.1` tag with DVC (see the DVC walkthrough).
