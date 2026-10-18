"""End-to-end checks of the publish -> rebuild loop, run on a temporary copy of the database."""
import shutil
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import rebuild_db

from glut_ews.common.contracts import check_output


@pytest.fixture
def sandbox(tmp_path):
    db = tmp_path / "glut_ews.duckdb"
    shutil.copy(ROOT / "data" / "glut_ews.duckdb", db)
    (tmp_path / "outputs").mkdir()
    (tmp_path / "docs").mkdir()
    args = ["--db", str(db), "--outputs-dir", str(tmp_path / "outputs"), "--parquet-dir", str(tmp_path / "parquet"),
            "--docs-dir", str(tmp_path / "docs"), "--no-backup"]
    return db, tmp_path, args


def _prediction_v1(db):
    with duckdb.connect(str(db), read_only=True) as con:
        df = con.sql("SELECT * FROM outputs.c3_risk_prediction").df()
    df["source_version"] = "v1"
    df["top_reasons"] = "test reason"
    return df


def test_v0_outputs_satisfy_contracts():
    with duckdb.connect(str(ROOT / "data" / "glut_ews.duckdb"), read_only=True) as con:
        seasons = set(con.sql("SELECT season FROM core.dim_season").df().season)
        for t in ["c1_glut_season", "c2_pressure_score", "c3_training_label", "c3_risk_prediction"]:
            errs, _ = check_output(con.sql(f"SELECT * FROM outputs.{t}").df(), t, seasons)
            assert not errs, (t, errs)


def test_valid_output_is_applied_and_v0_archived(sandbox):
    db, tmp, args = sandbox
    _prediction_v1(db).to_parquet(tmp / "outputs" / "c3_risk_prediction.parquet", index=False)
    assert rebuild_db.main(args) == 0
    with duckdb.connect(str(db), read_only=True) as con:
        assert con.sql("SELECT DISTINCT source_version FROM outputs.c3_risk_prediction").fetchall() == [("v1",)]
        assert con.sql("SELECT DISTINCT source_version FROM outputs_history.c3_risk_prediction").fetchall() == [
            ("v0",)]
        n_supply = con.sql("SELECT COUNT(*) FROM core.supply_season").fetchone()[0]
        assert con.sql("SELECT COUNT(*) FROM views.component4_dataset").fetchone()[0] == n_supply
    assert (tmp / "parquet" / "outputs" / "c3_risk_prediction.parquet").exists()
    assert rebuild_db.main(args) == 0          # idempotent: re-running does not duplicate history
    with duckdb.connect(str(db), read_only=True) as con:
        n_pred = con.sql("SELECT COUNT(*) FROM outputs.c3_risk_prediction").fetchone()[0]
        assert con.sql("SELECT COUNT(*) FROM outputs_history.c3_risk_prediction").fetchone()[0] == n_pred


def test_invalid_output_changes_nothing(sandbox):
    db, tmp, args = sandbox
    bad = _prediction_v1(db)
    bad.loc[0, "prob_high"] = 1.7
    bad.to_parquet(tmp / "outputs" / "c3_risk_prediction.parquet", index=False)
    assert rebuild_db.main(args) == 1
    with duckdb.connect(str(db), read_only=True) as con:
        assert con.sql("SELECT DISTINCT source_version FROM outputs.c3_risk_prediction").fetchall() == [
            ("v0",)]


def test_duplicate_keys_rejected(sandbox):
    db, tmp, args = sandbox
    df = _prediction_v1(db)
    pd.concat([df, df.head(3)]).to_parquet(tmp / "outputs" / "c3_risk_prediction.parquet", index=False)
    assert rebuild_db.main(args) == 1


def test_unknown_output_table_rejected(sandbox):
    db, tmp, args = sandbox
    _prediction_v1(db).to_parquet(tmp / "outputs" / "c9_unknown.parquet", index=False)
    assert rebuild_db.main(args) == 1


def test_outputs_outside_footprint_rejected(sandbox):
    db, tmp, args = sandbox
    df = _prediction_v1(db)
    df.loc[0, "district"] = "Colombo"          # Colombo grows none of the five crops in the footprint
    df.to_parquet(tmp / "outputs" / "c3_risk_prediction.parquet", index=False)
    assert rebuild_db.main(args) == 1
