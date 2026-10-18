# Parent dataset — quick reference

`data/glut_ews.duckdb` · crops: tomato, pumpkin, cucumber, winged bean, green chilli · 2018/19 Maha – 2025 Yala (weekly data 2019–2025) · 12 economic centres · district rows only where a crop is commercially cultivated (29 crop–district pairs).

## How it is built

`python scripts/build_db.py` creates a brand-new database from versioned inputs — `data/raw/extracts/`, `data/raw/sources/`, `data/reference/`, `data/config/`, `sql/schema.sql`, `sql/views.sql` and the seeded generator — then re-applies published module outputs. There are no migrations; a fresh build reproduces the committed database exactly (tested).

## Layers

| Schema | Content | Changed by |
|---|---|---|
| `raw` | Source extracts exactly as published (HARTI, DCS weekly retail, WFP market prices, DOA Crop Forecast, AgStat, Cost of Cultivation, weather) | Nobody |
| `core` | Standardised parent dataset: canonical names, consistent units, primary keys, crop–district footprint (`dim_crop_district`) | Schema owner: inputs + `scripts/build_db.py` (brand-new database) |
| `outputs` | Active module outputs (`c1_glut_season`, `c2_pressure_score`, `c3_training_label`, `c3_risk_prediction`, later `c4_advisory`); `v0` = generated starting outputs | Modules via `publish_output` + rebuild |
| `outputs_history` | Earlier output versions archived by the rebuild | Rebuild |
| `views` | `component1_dataset` … `component4_dataset`, defined in `sql/views.sql` | Schema owner |

Where each table's data comes from (published, derived or modelled) is documented in `docs/data_sources_and_methods.md`, including SQL for observed-only evaluation subsets.

## Footprint rule

Supply-side tables (`supply_season`, `planting_target_season`) and district-level outputs have rows only for pairs in `core.dim_crop_district`. A district that does not grow a crop has **no row** for it — never a zero. National totals (`national_supply_season`) still include minor cultivation elsewhere, so district sums are below national totals (about 53–68% of national extent).

## Quick start

```python
from glut_ews.common import load, lag_by_season

c3 = load("views.component3_dataset")
c3 = lag_by_season(c3, ["historical_glut_label", "harvest_wholesale_mean_rs_kg", "market_arrivals_t"],
                   ["district", "crop"], k=1)
train = c3[c3.split == "train"]
load("SELECT crop, district, status FROM core.dim_crop_district")
```

## Rules

1. Shared split (`core.dim_season.split`): train ≤ 2023 Yala · validation 2023/24 Maha – 2024 Yala · test 2024/25 Maha – 2025 Yala.
2. No look-ahead: lag same-season outcomes before predicting a season.
3. C4 consumes `outputs.c3_risk_prediction`, never `c3_training_label`.
4. Replace outputs with `publish_output(df, table, version="v1")` + `scripts/rebuild_db.py`.
5. Never edit the database or `parquet/` directly.

Validation results: `docs/validation_summary.md` · active versions: `docs/build_manifest.json`.
