"""A brand-new build must reproduce the shipped database (same seed, same inputs)."""
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_db

TABLES = ["core.supply_season", "core.planting_target_season", "core.market_prices_weekly", "core.market_arrivals_weekly",
          "core.weather_daily", "core.national_supply_season", "core.dim_crop_district",
          "outputs.c1_glut_season", "outputs.c2_pressure_score", "outputs.c3_risk_prediction"]


def test_fresh_build_reproduces_shipped_database(tmp_path):
    out = tmp_path / "glut_ews.duckdb"
    assert build_db.main(["--out", str(out), "--no-export"]) == 0
    new = duckdb.connect(str(out), read_only=True)
    new.execute(f"ATTACH '{(ROOT / 'data' / 'glut_ews.duckdb').as_posix()}' AS shipped (READ_ONLY)")
    for t in TABLES:
        diff = new.execute(f"SELECT COUNT(*) FROM (SELECT * FROM {t} EXCEPT ALL SELECT * FROM shipped.{t})").fetchone()[0]
        diff += new.execute(f"SELECT COUNT(*) FROM (SELECT * FROM shipped.{t} EXCEPT ALL SELECT * FROM {t})").fetchone()[0]
        assert diff == 0, t
    schemas = {r[0] for r in new.execute("SELECT schema_name FROM information_schema.schemata WHERE catalog_name = 'glut_ews'").fetchall()}
    assert "meta" not in schemas
