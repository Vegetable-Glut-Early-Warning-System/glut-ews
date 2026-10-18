"""One season-based train/validation/test split for the whole system (stored in core.dim_season)."""
from .db import load


def season_order() -> dict[str, int]:
    s = load("SELECT season FROM core.dim_season ORDER BY season_start")
    return {v: i for i, v in enumerate(s.season)}

def split_of() -> dict[str, str]:
    s = load("SELECT season, split FROM core.dim_season")
    return dict(zip(s.season, s.split))
