"""Rebuild the parent dataset (data/glut_ews.duckdb) and its Parquet exports.

What it does, in order:
  1. Reads module outputs from  data/outputs/<table>.parquet       (published with publish_output)
     and core corrections from   data/core_updates/<table>.parquet  (schema owner only)
  2. Validates everything first. If anything fails, nothing is changed.
  3. Backs up the database, then in one transaction:
       - archives the currently active output version into outputs_history.<table>
       - replaces outputs.<table> with the new version
       - replaces core.<table> with any core update
       - re-applies the view definitions in sql/views.sql
  4. Re-runs integrity checks (keys, names, view row uniqueness).
  5. Re-exports parquet/, refreshes docs/table_inventory.csv and docs/build_manifest.json.

Usage (from the project root, with no notebook holding the database open):
  python scripts/rebuild_db.py                 # apply pending files, rebuild, export
  python scripts/rebuild_db.py --check-only    # validate pending files, change nothing
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
from glut_ews.common.schema import KEYS, PROVENANCE, ValidationError, validate

EXPORT_SCHEMAS = ["raw", "core", "outputs", "outputs_history"]
VIEW_KEYS = {
    "component1_dataset": ["week_start_date", "economic_centre", "crop"],
    "component2_dataset": ["season", "district", "crop"],
    "component3_dataset": ["season", "district", "crop"],
    "component4_dataset": ["season", "district", "crop"],
}


def log(msg: str = "") -> None:
    print(msg, flush=True)


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--db", default=ROOT / "data" / "glut_ews.duckdb", type=Path)
    p.add_argument("--outputs-dir", default=ROOT / "data" / "outputs", type=Path)
    p.add_argument("--core-updates-dir", default=ROOT / "data" / "core_updates", type=Path)
    p.add_argument("--parquet-dir", default=ROOT / "parquet", type=Path)
    p.add_argument("--views-sql", default=ROOT / "sql" / "views.sql", type=Path)
    p.add_argument("--docs-dir", default=ROOT / "docs", type=Path)
    p.add_argument("--check-only", action="store_true", help="validate pending files only")
    p.add_argument("--no-export", action="store_true", help="skip parquet/ export")
    p.add_argument("--no-backup", action="store_true", help="skip database backup")
    p.add_argument("--csv", action="store_true", help="also export csv_view/ for viewing")
    return p.parse_args(argv)


def open_db(path: Path, read_only: bool):
    try:
        return duckdb.connect(str(path), read_only=read_only)
    except duckdb.IOException as e:
        log(f"\nCannot open {path}: {e}\nClose any notebook, DBeaver or Python session using the database and retry.")
        sys.exit(2)


def table_exists(con, schema: str, table: str) -> bool:
    return con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=? AND table_name=?",
                       [schema, table]).fetchone()[0] > 0


def collect(dirpath: Path) -> list[Path]:
    return sorted(p for p in dirpath.glob("*.parquet")) if dirpath.exists() else []


def check_core_update(con, path: Path) -> tuple[list[str], pd.DataFrame | None]:
    table = path.stem
    if not table_exists(con, "core", table):
        return [f"core.{table} does not exist (core updates can only replace existing core tables)"], None
    df = pd.read_parquet(path)
    current = [r[0] for r in con.execute(f"DESCRIBE core.{table}").fetchall()]
    errs = []
    if set(df.columns) != set(current):
        errs.append(f"columns differ from core.{table}: missing {sorted(set(current) - set(df.columns))}, "
                    f"unexpected {sorted(set(df.columns) - set(current))}")
        return errs, None
    df = df[current]
    if f"core.{table}" in KEYS:
        try:
            validate(df, f"core.{table}")
        except ValidationError as e:
            errs.append(str(e))
    if "provenance" in df.columns:
        if df["provenance"].isna().any():
            errs.append("provenance has missing values")
        bad = set(df["provenance"].dropna()) - PROVENANCE
        if bad:
            errs.append(f"unknown provenance values {bad}")
    if df.empty:
        errs.append("table is empty")
    return errs, df


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
        n = con.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchone()[0]
        c = len(con.execute(f"DESCRIBE {schema}.{table}").fetchall())
        inventory.append({"schema": schema, "table": table, "type": "view" if ttype == "VIEW" else "table",
                          "rows": n, "columns": c})
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
        con.sql(f"SELECT * FROM {schema}.{table}").df().to_csv(out / schema / f"{table}.csv", index=False,
                                                                 encoding="utf-8-sig")
    (out / "README.txt").write_text("Viewing copies only. Do not edit or use as model input.\n")
    log(f"  csv_view/ written ({sum(1 for _ in out.rglob('*.csv'))} files)")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    a = parse_args(argv)
    if not a.db.exists():
        log(f"Database not found: {a.db}. Run `dvc pull` first.")
        return 2
    log(f"Parent dataset: {a.db}")

    # ---- 1-2. collect and validate (read-only) ------------------------------------------
    con = open_db(a.db, read_only=True)
    seasons = set(con.sql("SELECT season FROM core.dim_season").df().season)
    out_files, core_files = collect(a.outputs_dir), collect(a.core_updates_dir)
    log(f"Pending: {len(out_files)} module output file(s), {len(core_files)} core update file(s)")
    errors, outputs, cores = [], {}, {}
    for f in out_files:
        df = pd.read_parquet(f)
        errs, warns = check_output(df, f.stem, seasons)
        for w in warns:
            log(f"  ! {f.name}: {w}")
        if errs:
            errors += [f"{f.name}: {e}" for e in errs]
        else:
            outputs[f.stem] = df[contract_columns(f.stem, df)]
            log(f"  ok  {f.name}: {len(df):,} rows, version {df['source_version'].iloc[0]}")
    for f in core_files:
        errs, df = check_core_update(con, f)
        if errs:
            errors += [f"core_updates/{f.name}: {e}" for e in errs]
        else:
            cores[f.stem] = df
            log(f"  ok  core_updates/{f.name}: {len(df):,} rows")
    current_versions = {}
    for t in CONTRACTS:
        if table_exists(con, "outputs", t):
            current_versions[t] = sorted(set(con.sql(f"SELECT DISTINCT source_version FROM outputs.{t}").df()
                                             .source_version))
    con.close()
    if errors:
        log("\nValidation failed - nothing was changed:")
        for e in errors:
            log(f"  x {e}")
        return 1
    if a.check_only:
        log("\nCheck only: all pending files are valid. Nothing was changed.")
        return 0

    # ---- 3. backup + apply in one transaction ------------------------------------------
    if not a.no_backup:
        bdir = a.db.parent / "backups"
        bdir.mkdir(exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(a.db, bdir / f"glut_ews_{stamp}.duckdb")
        for old in sorted(bdir.glob("glut_ews_*.duckdb"))[:-3]:
            old.unlink()
        log(f"Backup: data/backups/glut_ews_{stamp}.duckdb (last 3 kept)")

    con = open_db(a.db, read_only=False)
    try:
        con.execute("BEGIN TRANSACTION")
        con.execute("CREATE SCHEMA IF NOT EXISTS outputs_history")
        for t, df in outputs.items():
            new_v = df["source_version"].iloc[0]
            if table_exists(con, "outputs", t):
                if not table_exists(con, "outputs_history", t):
                    con.execute(f"CREATE TABLE outputs_history.{t} AS SELECT *, now() AS archived_at "
                                f"FROM outputs.{t} WHERE false")
                hist_cols = [r[0] for r in con.execute(f"DESCRIBE outputs_history.{t}").fetchall()]
                cur_cols = [r[0] for r in con.execute(f"DESCRIBE outputs.{t}").fetchall()]
                for col in cur_cols:
                    if col not in hist_cols:
                        typ = con.execute(f"SELECT data_type FROM information_schema.columns WHERE "
                                          f"table_schema='outputs' AND table_name='{t}' AND column_name='{col}'"
                                          ).fetchone()[0]
                        con.execute(f'ALTER TABLE outputs_history.{t} ADD COLUMN "{col}" {typ}')
                active = {r[0] for r in con.execute(f"SELECT DISTINCT source_version FROM outputs.{t}").fetchall()}
                archived = con.execute(
                    f"SELECT COUNT(*) FROM outputs_history.{t} WHERE source_version IN "
                    f"(SELECT DISTINCT source_version FROM outputs.{t})").fetchone()[0]
                if active != {new_v} and archived == 0:
                    cols = ", ".join(f'"{c}"' for c in cur_cols)
                    con.execute(f"INSERT INTO outputs_history.{t} ({cols}, archived_at) "
                                f"SELECT {cols}, now() FROM outputs.{t}")
            con.register("incoming", df)
            con.execute(f"CREATE OR REPLACE TABLE outputs.{t} AS SELECT * FROM incoming")
            con.unregister("incoming")
            log(f"  outputs.{t}: {current_versions.get(t, ['(new table)'])} -> ['{new_v}']")
        for t, df in cores.items():
            con.register("incoming", df)
            con.execute(f"CREATE OR REPLACE TABLE core.{t} AS SELECT * FROM incoming")
            con.unregister("incoming")
            log(f"  core.{t}: replaced ({len(df):,} rows)")
        con.execute(a.views_sql.read_text())
        log("  views re-applied from sql/views.sql")

        # ---- 4. integrity checks before committing ---------------------------------------
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
        con.close()
        raise

    # move applied core updates out of the pending folder
    if cores:
        applied = a.core_updates_dir / "applied"
        applied.mkdir(exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        for f in core_files:
            f.rename(applied / f"{stamp}_{f.name}")

    # ---- 5. exports and documentation --------------------------------------------------
    inventory = []
    if not a.no_export:
        inventory = export_parquet(con, a.parquet_dir)
        pd.DataFrame(inventory).to_csv(a.docs_dir / "table_inventory.csv", index=False)
        log(f"  parquet/ re-exported ({len(inventory)} tables/views)")
    if a.csv:
        export_csv(con, ROOT)
    active = {t: sorted(set(con.sql(f"SELECT DISTINCT source_version FROM outputs.{t}").df().source_version))
              for t in CONTRACTS if table_exists(con, "outputs", t)}
    con.close()
    manifest = {
        "built_at": dt.datetime.now().isoformat(timespec="seconds"),
        "database_sha256": sha256(a.db),
        "active_output_versions": active,
        "applied_output_files": sorted(outputs),
        "applied_core_updates": sorted(cores),
        "tables": inventory,
    }
    (a.docs_dir / "build_manifest.json").write_text(json.dumps(manifest, indent=2))
    log("\nRebuild complete. Next: dvc add data/glut_ews.duckdb parquet && git add . && "
        "git commit -m 'Rebuild dataset' && dvc push && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
