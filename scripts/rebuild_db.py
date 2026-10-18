"""Apply published module outputs to the parent dataset and refresh views and exports.

Day-to-day loop (no regeneration of core data):
  1. Reads module outputs from data/outputs/<table>.parquet (published with publish_output).
  2. Validates them against their contracts. If anything fails, nothing is changed.
  3. Backs up the database, then in one transaction archives the active version into
     outputs_history.<table>, loads the new version, re-applies sql/views.sql and runs integrity checks.
  4. Re-exports parquet/, docs/table_inventory.csv and docs/build_manifest.json.

Core data changes (sources, reference tables, footprint, generation method, schema) are made by
rebuilding the whole database from scratch: python scripts/build_db.py

Usage (from the project root, with no notebook holding the database open):
  python scripts/rebuild_db.py                 # apply published outputs, refresh views and exports
  python scripts/rebuild_db.py --check-only    # validate published outputs, change nothing
  python scripts/rebuild_db.py --csv           # also write csv_view/ for Excel viewing
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glut_ews.common.contracts import CONTRACTS, check_output, contract_columns
from glut_ews.common.schema import KEYS, ValidationError, validate

EXPORT_SCHEMAS = ["raw", "core", "outputs", "outputs_history"]
VIEW_KEYS = {
    "component1_dataset": ["week_start_date", "economic_centre", "crop"],
    "component2_dataset": ["season", "district", "crop"],
    "component3_dataset": ["season", "district", "crop"],
    "component4_dataset": ["season", "district", "crop"],
}


def log(msg: str = "") -> None:
    print(msg, flush=True)


def open_db(path: Path, read_only: bool):
    try:
        return duckdb.connect(str(path), read_only=read_only)
    except duckdb.IOException as e:
        log(f"\nCannot open {path}: {e}\nClose any notebook, DBeaver or Python session using the database and retry.")
        sys.exit(2)


def table_exists(con, schema: str, table: str) -> bool:
    return con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=? AND table_name=?",
                       [schema, table]).fetchone()[0] > 0


def validate_output_files(con, outputs_dir: Path) -> tuple[dict, list[str]]:
    """Read and validate every data/outputs/*.parquet. Returns ({table: df}, errors)."""
    seasons = set(con.sql("SELECT season FROM core.dim_season").df().season)
    found, errors = {}, []
    for f in sorted(outputs_dir.glob("*.parquet")) if outputs_dir.exists() else []:
        df = pd.read_parquet(f)
        errs, warns = check_output(df, f.stem, seasons)
        for w in warns:
            log(f"  ! {f.name}: {w}")
        if errs:
            errors += [f"{f.name}: {e}" for e in errs]
        else:
            found[f.stem] = df[contract_columns(f.stem, df)]
            log(f"  ok  {f.name}: {len(df):,} rows, version {df['source_version'].iloc[0]}")
    return found, errors


def apply_outputs(con, outputs: dict) -> None:
    """Load validated outputs (inside the caller's transaction), archiving the version they replace."""
    for t, df in outputs.items():
        new_v = df["source_version"].iloc[0]
        active = {r[0] for r in con.execute(f"SELECT DISTINCT source_version FROM outputs.{t}").fetchall()}
        if active and active != {new_v}:
            if not table_exists(con, "outputs_history", t):
                con.execute(f"CREATE TABLE outputs_history.{t} AS SELECT *, now() AS archived_at FROM outputs.{t} WHERE false")
            done = con.execute(f"SELECT COUNT(*) FROM outputs_history.{t} WHERE source_version IN "
                               f"(SELECT DISTINCT source_version FROM outputs.{t})").fetchone()[0]
            if not done:
                con.execute(f"INSERT INTO outputs_history.{t} BY NAME SELECT *, now() AS archived_at FROM outputs.{t}")
        con.register("incoming", df)
        con.execute(f"DELETE FROM outputs.{t}")
        con.execute(f"INSERT INTO outputs.{t} BY NAME SELECT * FROM incoming")
        con.unregister("incoming")
        log(f"  outputs.{t}: {sorted(active) or ['(empty)']} -> ['{new_v}']")


def integrity_checks(con) -> list[str]:
    errs = []
    for t in KEYS:
        schema, name = t.split(".")
        if not table_exists(con, schema, name):
            continue
        try:
            validate(con.sql(f"SELECT * FROM {t}").df(), t)
        except ValidationError as e:
            errs.append(str(e))
    for t in ["core.supply_season", "core.planting_target_season", "outputs.c2_pressure_score",
              "outputs.c3_training_label", "outputs.c3_risk_prediction"]:
        s, n = t.split(".")
        if table_exists(con, s, n):
            bad = con.execute(f"SELECT COUNT(*) FROM {t} ANTI JOIN core.dim_crop_district USING (crop, district)").fetchone()[0]
            if bad:
                errs.append(f"{t}: {bad} rows for crop-district pairs outside core.dim_crop_district")
    for t, col in [("core.supply_season", "extent_ha"), ("core.supply_season", "production_t"),
                   ("core.planting_target_season", "target_ha"), ("core.market_prices_weekly", "wholesale_price_rs_kg"),
                   ("core.market_prices_weekly", "retail_price_rs_kg"), ("core.market_arrivals_weekly", "arrivals_t")]:
        bad = con.execute(f"SELECT COUNT(*) FROM {t} WHERE {col} IS NULL OR {col} <= 0").fetchone()[0]
        if bad:
            errs.append(f"{t}.{col}: {bad} null, zero or negative values")
    bad = con.execute("SELECT COUNT(*) FROM core.market_prices_weekly WHERE wholesale_price_rs_kg > retail_price_rs_kg").fetchone()[0]
    if bad:
        errs.append(f"core.market_prices_weekly: {bad} rows with wholesale above retail")
    for v, keys in VIEW_KEYS.items():
        k = ", ".join(keys)
        n, d = con.execute(f"SELECT COUNT(*), COUNT(DISTINCT ({k})) FROM views.{v}").fetchone()
        if n == 0:
            errs.append(f"views.{v} returns no rows")
        elif n != d:
            errs.append(f"views.{v} has {n - d} duplicated rows (check output keys / join logic)")
    return errs


def export_parquet(con, parquet_dir: Path) -> list[dict]:
    rows = con.execute(
        "SELECT table_schema, table_name, table_type FROM information_schema.tables "
        f"WHERE table_schema IN ({', '.join(repr(s) for s in EXPORT_SCHEMAS)}) "
        "OR (table_schema='views' AND table_name LIKE 'component%') ORDER BY 1, 2").fetchall()
    keep, inventory = set(), []
    for schema, table, ttype in rows:
        out = parquet_dir / schema / f"{table}.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        con.execute(f"COPY (SELECT * FROM {schema}.{table}) TO '{out.as_posix()}' (FORMAT PARQUET)")
        keep.add(out.resolve())
        inventory.append({"schema": schema, "table": table, "type": "view" if ttype == "VIEW" else "table",
                          "rows": con.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchone()[0],
                          "columns": len(con.execute(f"DESCRIBE {schema}.{table}").fetchall())})
    for f in parquet_dir.rglob("*.parquet"):
        if f.resolve() not in keep:
            f.unlink()
            log(f"  removed stale export {f.relative_to(parquet_dir)}")
    return inventory


def export_csv(con, root: Path) -> None:
    out = root / "csv_view"
    shutil.rmtree(out, ignore_errors=True)
    for schema, table in con.execute(
            "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema IN "
            "('raw','core','outputs','outputs_history') OR (table_schema='views' AND table_name LIKE 'component%')").fetchall():
        (out / schema).mkdir(parents=True, exist_ok=True)
        con.sql(f"SELECT * FROM {schema}.{table}").df().to_csv(out / schema / f"{table}.csv", index=False, encoding="utf-8-sig")
    (out / "README.txt").write_text("Viewing copies only. Do not edit or use as model input.\n")
    log(f"  csv_view/ written ({sum(1 for _ in out.rglob('*.csv'))} files)")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_exports(db: Path, parquet_dir: Path, docs_dir: Path, csv: bool, extra: dict | None = None) -> None:
    con = open_db(db, read_only=True)
    inventory = export_parquet(con, parquet_dir)
    pd.DataFrame(inventory).to_csv(docs_dir / "table_inventory.csv", index=False)
    log(f"  parquet/ re-exported ({len(inventory)} tables/views)")
    if csv:
        export_csv(con, ROOT)
    active = {t: sorted(set(con.sql(f"SELECT DISTINCT source_version FROM outputs.{t}").df().source_version))
              for t in CONTRACTS if table_exists(con, "outputs", t)}
    con.close()
    manifest = {"built_at": dt.datetime.now().isoformat(timespec="seconds"), "database_sha256": sha256(db),
                "active_output_versions": active, **(extra or {}), "tables": inventory}
    (docs_dir / "build_manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n")


def backup(db: Path, keep: int = 3) -> None:
    bdir = db.parent / "backups"
    bdir.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(db, bdir / f"glut_ews_{stamp}.duckdb")
    for old in sorted(bdir.glob("glut_ews_*.duckdb"))[:-keep]:
        old.unlink()
    log(f"Backup: data/backups/glut_ews_{stamp}.duckdb (last {keep} kept)")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--db", default=ROOT / "data" / "glut_ews.duckdb", type=Path)
    p.add_argument("--outputs-dir", default=ROOT / "data" / "outputs", type=Path)
    p.add_argument("--parquet-dir", default=ROOT / "parquet", type=Path)
    p.add_argument("--views-sql", default=ROOT / "sql" / "views.sql", type=Path)
    p.add_argument("--docs-dir", default=ROOT / "docs", type=Path)
    p.add_argument("--check-only", action="store_true")
    p.add_argument("--no-export", action="store_true")
    p.add_argument("--no-backup", action="store_true")
    p.add_argument("--csv", action="store_true")
    a = p.parse_args(argv)
    if not a.db.exists():
        log(f"Database not found: {a.db}. Run `dvc pull` or `python scripts/build_db.py`.")
        return 2
    log(f"Parent dataset: {a.db}")
    con = open_db(a.db, read_only=True)
    outputs, errors = validate_output_files(con, a.outputs_dir)
    con.close()
    if errors:
        log("\nValidation failed - nothing was changed:")
        for e in errors:
            log(f"  x {e}")
        return 1
    log(f"Published outputs to apply: {len(outputs)}")
    if a.check_only:
        log("\nCheck only: all published outputs are valid. Nothing was changed.")
        return 0
    if not a.no_backup:
        backup(a.db)
    con = open_db(a.db, read_only=False)
    try:
        con.execute("BEGIN TRANSACTION")
        apply_outputs(con, outputs)
        con.execute(a.views_sql.read_text())
        log("  views re-applied from sql/views.sql")
        errs = integrity_checks(con)
        if errs:
            con.execute("ROLLBACK")
            log("\nIntegrity checks failed - all changes rolled back:")
            for e in errs:
                log(f"  x {e}")
            return 1
        con.execute("COMMIT")
        log("  integrity checks passed, changes committed")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    if not a.no_export:
        write_exports(a.db, a.parquet_dir, a.docs_dir, a.csv, {"applied_output_files": sorted(outputs)})
    log("\nDone. Next: dvc add data/glut_ews.duckdb parquet && git add . && git commit && dvc push && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
