"""Module side of the loop: validate an output and save it to data/outputs/ for the next rebuild."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .contracts import CONTRACTS, check_output, contract_columns
from .db import DB_PATH, load

OUTPUTS_DIR = DB_PATH.parent / "outputs"


class ContractError(ValueError):
    pass


def publish_output(df: pd.DataFrame, table: str, version: str, outputs_dir: Path | str = OUTPUTS_DIR) -> Path:
    """Validate `df` against the contract for `table` and write data/outputs/<table>.parquet.

    version: e.g. "v1", "v1.1". "v0" is reserved for the generated starting outputs.
    After publishing: `dvc add data/outputs/<table>.parquet`, commit, push, and ask the
    schema owner to run `python scripts/rebuild_db.py`.
    """
    if not version or version == "v0":
        raise ContractError("'v0' is reserved for the generated starting outputs; use 'v1' or later")
    out = df.copy()
    out["source_version"] = version
    seasons = set(load("SELECT season FROM core.dim_season").season)
    errs, warns = check_output(out, table, seasons)
    for w in warns:
        print(f"  warning: {w}")
    if errs:
        raise ContractError(f"{table} does not match its contract:\n  - " + "\n  - ".join(errs))
    out = out[contract_columns(table, out)]
    path = Path(outputs_dir) / f"{table}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    print(f"Published {len(out):,} rows -> {path}  (owner {CONTRACTS[table]['owner']}, version {version})")
    print(f"Next: dvc add {path.relative_to(DB_PATH.parents[1]) if path.is_relative_to(DB_PATH.parents[1]) else path}"
          " && git add . && git commit && dvc push && git push")
    return path
