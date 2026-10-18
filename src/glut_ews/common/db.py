"""Single access point to the parent dataset."""
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "glut_ews.duckdb"

def connect(read_only: bool = True, path: Path | str = DB_PATH) -> duckdb.DuckDBPyConnection:
    """Open the parent dataset. Modules read with read_only=True; only the
    module that owns an outputs.* table opens it writable to replace it."""
    return duckdb.connect(str(path), read_only=read_only)

def load(table_or_sql: str, con: duckdb.DuckDBPyConnection | None = None):
    """Return a pandas DataFrame from 'schema.table' or a full SQL query."""
    own = con is None
    con = con or connect()
    q = table_or_sql if table_or_sql.strip().lower().startswith(("select", "with")) else f"SELECT * FROM {table_or_sql}"
    df = con.sql(q).df()
    if own:
        con.close()
    return df
