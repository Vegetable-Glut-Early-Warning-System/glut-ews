"""Point-in-time helpers: features for season t may only use information available before t starts."""
import pandas as pd

from .splits import season_order


def add_season_index(df: pd.DataFrame, col: str = "season") -> pd.DataFrame:
    order = season_order()
    out = df.copy()
    out["season_idx"] = out[col].map(order)
    if out["season_idx"].isna().any():
        raise ValueError("unknown season labels")
    return out

def lag_by_season(df: pd.DataFrame, cols: list[str], group: list[str], k: int = 1, suffix: str | None = None) -> pd.DataFrame:
    """Shift `cols` back by k seasons within `group` (k=1 previous season, k=2 same season last year).
    Rows are aligned on the season index, so gaps in the panel never shift values to the wrong season."""
    out = add_season_index(df)
    src = out[group + ["season_idx"] + cols].copy()
    src["season_idx"] = src["season_idx"] + k
    src = src.rename(columns={c: f"{c}{suffix or f'_lag{k}'}" for c in cols})
    return out.merge(src, on=group + ["season_idx"], how="left")
