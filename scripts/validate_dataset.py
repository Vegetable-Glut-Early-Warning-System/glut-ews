"""Write docs/validation_summary.md and refresh docs/data_dictionary.csv from the current database.

Run after scripts/rebuild_db.py:
    python scripts/validate_dataset.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
YIELD_BOUNDS = {"Tomato": (8, 30), "Pumpkin": (7, 22), "Cucumber": (7, 22), "Winged bean": (5, 14), "Green chilli": (3, 10)}

DESC = {
    "season": "Season label, e.g. 2024/25 Maha (Oct-Mar) or 2025 Yala (Apr-Sep)", "season_type": "Maha or Yala",
    "season_year": "Starting calendar year of the season", "district": "Administrative district (canonical spelling)",
    "crop": "Tomato, Pumpkin, Cucumber, Winged bean, Green chilli", "economic_centre": "Dedicated economic centre",
    "week_start_date": "Start of 7-day week block (week 1 starts 1 Jan; week 52 spans 8-9 days)", "year": "Calendar year",
    "week": "Week number 1-52", "extent_ha": "Cultivated extent (ha)", "production_t": "Production (t)",
    "yield_t_ha": "Yield (t/ha)", "target_ha": "DOA planting target (ha)", "farmgate_rs_kg": "Farm-gate price (Rs/kg)",
    "unit_cost_rs_kg": "Cost of production per kg incl. imputed cost (Rs/kg)",
    "wholesale_price_rs_kg": "Weekly average wholesale price (Rs/kg)", "retail_price_rs_kg": "Weekly average retail price (Rs/kg)",
    "arrivals_t": "Weekly arrivals at the centre (t)", "wastage_t": "Weekly market wastage at the centre (t)",
    "harvest_t": "Weekly national harvest (t)", "farm_transport_loss_t": "Weekly loss before reaching market (t)",
    "rainfall_mm": "Rainfall (mm)", "temp_mean_c": "Mean air temperature (C)", "temp_max_c": "Maximum air temperature (C)",
    "et0_mm": "FAO reference evapotranspiration (mm)", "ccpi_2021_100": "Colombo Consumer Price Index (2021=100)",
    "weight": "Share of the district's DEC-bound output going to the centre", "status": "core (team field list) or proposed (added on evidence)",
    "justification": "Why the district is in the footprint", "source": "Evidence / source",
    "glut_weeks": "Harvest-window weeks with seasonally adjusted real price < 70% of normal",
    "weeks_observed": "Harvest-window weeks with a price", "historical_glut_label": "Glut if glut_weeks >= 4, else No glut",
    "cobweb_index": "ln(previous-season harvest real price / mean of the 3 seasons before it)",
    "supply_pressure_score": "0-100 entropy-weighted pre-planting supply pressure score",
    "pressure_class": "Low / Medium / High (50th / 80th percentile)", "top_drivers": "Largest contributions to the score",
    "glut_risk_label": "Realised glut risk class: Low / Medium / High", "predicted_risk_label": "Predicted glut risk class",
    "prob_low": "Predicted probability Low", "prob_medium": "Predicted probability Medium", "prob_high": "Predicted probability High",
    "top_reasons": "Plain-language reasons for the prediction", "source_version": "Output version (v0 = generated starting output; v1+ = module result)",
    "split": "train / validation / test (season-based, shared by all modules)",
}


def md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        lines.append("| " + " | ".join("" if pd.isna(v) else (f"{v:,.0f}" if isinstance(v, float) and float(v).is_integer() else f"{v:,.2f}" if isinstance(v, float) else str(v)) for v in r) + " |")
    return "\n".join(lines)


def main() -> int:
    con = duckdb.connect(str(ROOT / "data" / "glut_ews.duckdb"), read_only=True)
    q = lambda s: con.sql(s).df()
    out = ["# Validation summary", "", "Generated from `data/glut_ews.duckdb` by `scripts/validate_dataset.py`.", ""]

    out += ["## 1. Crop-district footprint", ""]
    out += [md(q("SELECT crop, string_agg(district, ', ' ORDER BY district) FILTER (WHERE status='core') AS core, "
                 "string_agg(district, ', ' ORDER BY district) FILTER (WHERE status='proposed') AS proposed, COUNT(*) AS districts "
                 "FROM core.dim_crop_district GROUP BY crop ORDER BY crop")), ""]

    out += ["## 2. Rows per crop and district (core.supply_season, 14 seasons)", ""]
    rc = q("SELECT district, crop, COUNT(*) n FROM core.supply_season GROUP BY ALL").pivot(index="district", columns="crop", values="n")
    out += [md(rc.reset_index().fillna("—")), "", "— = no rows (district does not cultivate the crop).", ""]

    out += ["## 3. Extent and production by district (mean per season)", ""]
    out += [md(q("SELECT crop, district, ROUND(AVG(extent_ha),1) AS mean_extent_ha, ROUND(AVG(production_t),0) AS mean_production_t, "
                 "COUNT(*) AS seasons FROM core.supply_season GROUP BY ALL ORDER BY crop, mean_extent_ha DESC")), ""]

    out += ["## 4. Yield ranges per crop (t/ha)", ""]
    y = q("SELECT crop, MIN(yield_t_ha) AS min, MEDIAN(yield_t_ha) AS median, MAX(yield_t_ha) AS max, COUNT(DISTINCT yield_t_ha) AS distinct_values, COUNT(*) AS rows "
          "FROM core.supply_season GROUP BY crop ORDER BY crop")
    y["plausible_range"] = y.crop.map(lambda c: f"{YIELD_BOUNDS[c][0]}-{YIELD_BOUNDS[c][1]}")
    y["within_range"] = [(YIELD_BOUNDS[c][0] <= lo and hi <= YIELD_BOUNDS[c][1]) for c, lo, hi in zip(y.crop, y["min"], y["max"])]
    out += [md(y), ""]

    out += ["## 5. Seasonality: share of annual extent planted in Maha (footprint districts)", ""]
    out += [md(q("SELECT crop, ROUND(SUM(extent_ha) FILTER (WHERE season LIKE '%Maha') / SUM(extent_ha), 2) AS maha_share "
                 "FROM core.supply_season GROUP BY crop ORDER BY crop")), ""]

    out += ["## 6. Price ranges (Rs/kg, 2019-2025)", ""]
    out += [md(q("SELECT crop, ROUND(MIN(wholesale_price_rs_kg),0) AS wholesale_min, ROUND(MEDIAN(wholesale_price_rs_kg),0) AS wholesale_median, "
                 "ROUND(MAX(wholesale_price_rs_kg),0) AS wholesale_max, ROUND(MIN(retail_price_rs_kg),0) AS retail_min, "
                 "ROUND(MEDIAN(retail_price_rs_kg),0) AS retail_median, ROUND(MAX(retail_price_rs_kg),0) AS retail_max, "
                 "COUNT(DISTINCT economic_centre) AS centres FROM core.market_prices_weekly GROUP BY crop ORDER BY crop")), ""]
    out += ["### Mean wholesale price relative to Peliyagoda (Colombo)", ""]
    rel = q("""SELECT a.economic_centre, a.crop, ROUND(AVG(a.wholesale_price_rs_kg / b.wholesale_price_rs_kg), 3) AS r
               FROM core.market_prices_weekly a JOIN core.market_prices_weekly b
                 ON a.week_start_date = b.week_start_date AND a.crop = b.crop AND b.economic_centre = 'Peliyagoda'
               GROUP BY ALL""").pivot(index="economic_centre", columns="crop", values="r")
    out += [md(rel.reset_index().fillna("—")), "", "— = crop not traded at that centre (no rows).", ""]

    out += ["## 7. Row counts per table", ""]
    out += [md(q("SELECT schema_name AS schema, table_name AS table, estimated_size AS rows, column_count AS columns "
                 "FROM duckdb_tables() WHERE schema_name IN ('raw','core','outputs') ORDER BY 1, 2")), ""]

    checks = [
        ("Supply rows outside the footprint", "SELECT COUNT(*) FROM core.supply_season ANTI JOIN core.dim_crop_district USING (crop, district)"),
        ("Target rows outside the footprint", "SELECT COUNT(*) FROM core.planting_target_season ANTI JOIN core.dim_crop_district USING (crop, district)"),
        ("C2/C3 output rows outside the footprint", (
            "SELECT (SELECT COUNT(*) FROM outputs.c2_pressure_score ANTI JOIN core.dim_crop_district USING (crop, district)) + "
            "(SELECT COUNT(*) FROM outputs.c3_risk_prediction ANTI JOIN core.dim_crop_district USING (crop, district))")),
        ("Zero / negative extent, production or yield", "SELECT COUNT(*) FROM core.supply_season WHERE extent_ha <= 0 OR production_t <= 0 OR yield_t_ha <= 0"),
        ("Production inconsistent with extent x yield (> 0.05 t/ha)", "SELECT COUNT(*) FROM core.supply_season WHERE ABS(production_t / extent_ha - yield_t_ha) > 0.05"),
        ("Wholesale above retail", "SELECT COUNT(*) FROM core.market_prices_weekly WHERE wholesale_price_rs_kg > retail_price_rs_kg"),
        ("Null or non-positive prices", "SELECT COUNT(*) FROM core.market_prices_weekly WHERE NOT (wholesale_price_rs_kg > 0 AND retail_price_rs_kg > 0)"),
        ("Dates outside 2019-01-01 to 2025-12-31", "SELECT COUNT(*) FROM core.market_prices_weekly WHERE week_start_date NOT BETWEEN DATE '2019-01-01' AND DATE '2025-12-31'"),
        ("Arrivals rows without a matching price row", "SELECT COUNT(*) FROM core.market_arrivals_weekly ANTI JOIN core.market_prices_weekly USING (week_start_date, economic_centre, crop)"),
        ("Zero-arrival rows", "SELECT COUNT(*) FROM core.market_arrivals_weekly WHERE arrivals_t <= 0"),
        ("Columns named provenance / note / synthetic", (
            "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema IN ('core','outputs','views') "
            "AND column_name IN ('provenance','note','synthetic','is_synthetic')")),
    ]
    out += ["## 8. Integrity checks", "", "| Check | Violations |", "|---|---|"]
    ok = True
    for name, sql in checks:
        n = con.execute(sql).fetchone()[0]
        ok &= n == 0
        out.append(f"| {name} | {n} |")
    out += ["", "**All checks passed.**" if ok else "**Some checks failed — see above.**", ""]
    (ROOT / "docs" / "validation_summary.md").write_text("\n".join(out))

    rows = []
    for s, t, ttype in con.execute("SELECT table_schema, table_name, table_type FROM information_schema.tables WHERE table_schema IN "
                                   "('raw','core','outputs','outputs_history','views') ORDER BY 1, 2").fetchall():
        for c in con.execute(f"DESCRIBE {s}.{t}").fetchall():
            rows.append({"schema": s, "table": t, "object_type": "view" if ttype == "VIEW" else "table",
                         "column": c[0], "dtype": c[1], "description": DESC.get(c[0], "")})
    pd.DataFrame(rows).to_csv(ROOT / "docs" / "data_dictionary.csv", index=False)
    for t, f in [("core.known_issues", "known_issues.csv"), ("core.model_parameters", "model_parameters.csv"),
                 ("core.dim_crop_district", "crop_district_footprint.csv")]:
        q(f"SELECT * FROM {t}").to_csv(ROOT / "docs" / f, index=False)
    con.close()
    print(f"docs/validation_summary.md written ({'all checks passed' if ok else 'FAILURES'})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
