import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from glut_ews.common import lag_by_season, load, validate
from glut_ews.common.schema import KEYS


def test_core_tables_validate():
    for t in KEYS:
        validate(load(t), t)

def test_split_is_temporal():
    s = load("SELECT season, split FROM core.dim_season ORDER BY season_start")
    order = {"train": 0, "validation": 1, "test": 2}
    assert list(s.split.map(order)) == sorted(s.split.map(order))

def test_lag_never_uses_future():
    df = load("SELECT season, district, crop, extent_ha FROM core.supply_season")
    out = lag_by_season(df, ["extent_ha"], ["district", "crop"], k=2)
    first = out[out.season_idx < 2]
    assert first["extent_ha_lag2"].isna().all()
