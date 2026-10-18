"""Realism rules from the dataset audit, enforced on every test run."""
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
YIELD_BOUNDS = {"Tomato": (8, 30), "Pumpkin": (7, 22), "Cucumber": (7, 22), "Winged bean": (5, 14), "Green chilli": (3, 10)}


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(ROOT / "data" / "glut_ews.duckdb"), read_only=True)
    yield c
    c.close()


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def test_no_row_level_label_columns(con):
    assert one(con, "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema IN ('core','outputs','views') "
                    "AND column_name IN ('provenance','note','is_synthetic','synthetic')") == 0


def test_supply_only_in_footprint(con):
    for t in ["core.supply_season", "core.planting_target_season", "outputs.c2_pressure_score",
              "outputs.c3_training_label", "outputs.c3_risk_prediction", "views.component3_dataset"]:
        assert one(con, f"SELECT COUNT(*) FROM {t} ANTI JOIN core.dim_crop_district USING (crop, district)") == 0, t


def test_footprint_contains_team_core_list(con):
    core = {("Tomato", d) for d in ["Badulla", "Nuwara Eliya", "Kandy", "Matale"]} | \
           {("Pumpkin", d) for d in ["Anuradhapura", "Monaragala", "Ampara", "Hambantota", "Kurunegala"]} | \
           {("Green chilli", d) for d in ["Anuradhapura", "Puttalam", "Monaragala", "Kurunegala", "Hambantota", "Ampara"]} | \
           {("Cucumber", d) for d in ["Ampara", "Hambantota", "Kurunegala", "Monaragala", "Anuradhapura"]} | \
           {("Winged bean", d) for d in ["Matale", "Kurunegala", "Hambantota", "Anuradhapura"]}
    have = set(con.execute("SELECT crop, district FROM core.dim_crop_district WHERE status='core'").fetchall())
    assert core == have


def test_no_zero_or_placeholder_rows(con):
    assert one(con, "SELECT COUNT(*) FROM core.supply_season WHERE extent_ha <= 0 OR production_t <= 0 OR yield_t_ha <= 0") == 0
    assert one(con, "SELECT COUNT(*) FROM core.market_arrivals_weekly WHERE arrivals_t <= 0") == 0


def test_yields_in_agronomic_range_and_consistent(con):
    rows = con.execute("SELECT crop, MIN(yield_t_ha), MAX(yield_t_ha), MAX(ABS(production_t / extent_ha - yield_t_ha)) "
                       "FROM core.supply_season GROUP BY crop").fetchall()
    for crop, lo, hi, err in rows:
        blo, bhi = YIELD_BOUNDS[crop]
        assert blo <= lo and hi <= bhi, crop
        assert err < 0.05, crop


def test_yield_not_uniform(con):
    assert one(con, "SELECT MIN(n) FROM (SELECT crop, COUNT(DISTINCT yield_t_ha) n FROM core.national_supply_season GROUP BY crop)") >= 10


def test_prices_plausible(con):
    assert one(con, "SELECT COUNT(*) FROM core.market_prices_weekly WHERE wholesale_price_rs_kg > retail_price_rs_kg") == 0
    assert one(con, "SELECT COUNT(*) FROM core.market_prices_weekly WHERE wholesale_price_rs_kg < 5 OR retail_price_rs_kg > 3000") == 0
    assert one(con, "SELECT COUNT(*) FROM core.market_prices_weekly WHERE week_start_date < DATE '2019-01-01' "
                    "OR week_start_date > DATE '2025-12-31'") == 0


def test_centre_prices_not_constant_multiples(con):
    cv = one(con, """WITH p AS (SELECT a.week_start_date, a.economic_centre, a.crop,
                            a.wholesale_price_rs_kg / b.wholesale_price_rs_kg AS r
                     FROM core.market_prices_weekly a JOIN core.market_prices_weekly b
                       ON a.week_start_date = b.week_start_date AND a.crop = b.crop AND b.economic_centre = 'Peliyagoda'
                     WHERE a.economic_centre NOT IN ('Peliyagoda'))
                     SELECT MEDIAN(c) FROM (SELECT STDDEV(r) / AVG(r) AS c FROM p GROUP BY economic_centre, crop)""")
    assert 0.06 < cv < 0.18      # WFP observed market/Colombo ratio CV: median 0.117, IQR 0.083-0.147


def test_not_a_full_grid(con):
    assert one(con, "SELECT COUNT(*) FROM core.supply_season") < 25 * 5 * 14
    assert one(con, "SELECT COUNT(DISTINCT economic_centre || crop) FROM core.market_prices_weekly") < 12 * 5


def test_names_link_to_reference_tables(con):
    assert one(con, "SELECT COUNT(*) FROM core.dim_crop_district ANTI JOIN core.dim_district USING (district)") == 0
    assert one(con, "SELECT COUNT(*) FROM core.market_prices_weekly ANTI JOIN core.dim_economic_centre USING (economic_centre)") == 0
    assert one(con, "SELECT COUNT(*) FROM core.market_arrivals_weekly a ANTI JOIN core.market_prices_weekly p "
                    "USING (week_start_date, economic_centre, crop)") == 0
