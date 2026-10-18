"""Build the parent dataset (data/glut_ews.duckdb) as a brand-new database from its inputs.

Inputs (all versioned):
  data/raw/extracts/*.parquet        source extracts as published            (DVC)
  data/raw/sources/*.csv             WFP market prices, DCS weekly retail     (DVC)
  data/reference/*.csv               curated reference tables                 (Git)
  data/config/crop_district_footprint.csv                                     (Git)
  sql/schema.sql, sql/views.sql      table and view definitions               (Git)
  src/glut_ews/build/generator.py    generation of modelled tables, seed 20261018
  data/outputs/*.parquet             module outputs published as v1+ (re-applied on top of v0)

Steps: create empty database -> schema -> raw -> reference -> generate (core + v0 outputs) -> views ->
re-apply published outputs -> integrity checks -> replace the old database -> export parquet/ and docs.
The build happens in a temporary file; the existing database is only replaced if every check passes.

Usage (from the project root, with no notebook holding the database open):
  python scripts/build_db.py                       # build data/glut_ews.duckdb
  python scripts/build_db.py --exclude-proposed    # footprint = team core list only
  python scripts/build_db.py --out /tmp/test.duckdb --no-export
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import rebuild_db as rb

from glut_ews.build.generator import SEED, generate

REFERENCE_TABLES = ["dim_crop", "dim_district", "dim_economic_centre", "dim_season", "dim_calendar",
                    "bridge_district_centre", "cost_season", "macro_monthly"]
CSV_SOURCES = {"wfp_market_prices": ("wfp_food_prices_lk.csv", ""),
               "dcs_weekly_retail_prices": ("dcs_weekly_retail_prices.csv", ", all_varchar = true")}


def insert(con, table: str, df) -> None:
    con.register("incoming", df)
    con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM incoming")
    con.unregister("incoming")


def build(out: Path, seed: int, exclude_proposed: bool) -> tuple[int, dict]:
    tmp = out.with_name(out.stem + ".building.duckdb")
    for f in (tmp, tmp.with_name(tmp.name + ".wal")):
        f.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    rb.log(f"Building a new database: {tmp.name}")
    con.execute((ROOT / "sql" / "schema.sql").read_text())
    rb.log("  schema applied from sql/schema.sql")

    con.execute("CREATE SCHEMA raw")
    for f in sorted((ROOT / "data" / "raw" / "extracts").glob("*.parquet")):
        con.execute(f"CREATE TABLE raw.{f.stem} AS SELECT * FROM read_parquet('{f.as_posix()}')")
    for table, (fname, opts) in CSV_SOURCES.items():
        path = (ROOT / "data" / "raw" / "sources" / fname).as_posix()
        con.execute(f"CREATE TABLE raw.{table} AS SELECT * FROM read_csv_auto('{path}', header = true{opts})")
    n_raw = con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='raw'").fetchone()[0]
    rb.log(f"  raw: {n_raw} tables loaded")

    for t in REFERENCE_TABLES:
        path = (ROOT / "data" / "reference" / f"{t}.csv").as_posix()
        con.execute(f"INSERT INTO core.{t} BY NAME SELECT * FROM read_csv_auto('{path}', header = true)")
    rb.log(f"  reference: {len(REFERENCE_TABLES)} tables loaded from data/reference/")

    rb.log(f"  generating modelled tables (seed {seed}) ...")
    core, outputs, report = generate(con, seed=seed, exclude_proposed=exclude_proposed, log=rb.log)
    for t, df in core.items():
        insert(con, f"core.{t}", df)
    for t, df in outputs.items():
        insert(con, f"outputs.{t}", df)
    con.execute((ROOT / "sql" / "views.sql").read_text())
    rb.log("  views applied from sql/views.sql")

    published, errors = rb.validate_output_files(con, ROOT / "data" / "outputs")
    if errors:
        con.close()
        tmp.unlink()
        rb.log("\nPublished module outputs failed validation - build stopped, existing database untouched:")
        for e in errors:
            rb.log(f"  x {e}")
        return 1, report
    if published:
        rb.log("  re-applying published module outputs:")
        rb.apply_outputs(con, published)

    errs = rb.integrity_checks(con)
    con.close()
    if errs:
        tmp.unlink()
        rb.log("\nIntegrity checks failed - build stopped, existing database untouched:")
        for e in errs:
            rb.log(f"  x {e}")
        return 1, report
    rb.log("  integrity checks passed")
    if out.exists():
        rb.backup(out)
    os.replace(tmp, out)
    report["published_outputs_reapplied"] = sorted(published)
    return 0, report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--out", type=Path, default=ROOT / "data" / "glut_ews.duckdb")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--exclude-proposed", action="store_true", help="use only the team's core footprint")
    p.add_argument("--no-export", action="store_true", help="skip parquet/ and docs exports")
    p.add_argument("--csv", action="store_true", help="also write csv_view/")
    a = p.parse_args(argv)
    t0 = time.time()
    code, report = build(a.out, a.seed, a.exclude_proposed)
    if code:
        return code
    if not a.no_export:
        (ROOT / "docs" / "generation_report.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
        rb.write_exports(a.out, ROOT / "parquet", ROOT / "docs", a.csv,
                         {"seed": a.seed, "proposed_included": not a.exclude_proposed, "build": "from scratch"})
    rb.log(f"\nBuilt {a.out.relative_to(ROOT) if a.out.is_relative_to(ROOT) else a.out} in {time.time() - t0:.0f}s. "
           "Next: python scripts/validate_dataset.py && pytest -q, then dvc add data/glut_ews.duckdb parquet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
