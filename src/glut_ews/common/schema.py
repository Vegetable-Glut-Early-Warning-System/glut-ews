"""Shared vocabulary and lightweight validation (no extra dependencies)."""
import pandas as pd

CROPS = ["Tomato", "Pumpkin", "Cucumber", "Winged bean", "Green chilli"]
DISTRICTS = ["Colombo","Gampaha","Kalutara","Kandy","Matale","Nuwara Eliya","Galle","Matara","Hambantota",
             "Jaffna","Kilinochchi","Mannar","Vavuniya","Mullaitivu","Batticaloa","Ampara","Trincomalee",
             "Kurunegala","Puttalam","Anuradhapura","Polonnaruwa","Badulla","Monaragala","Ratnapura","Kegalle"]
CENTRES = ["Dambulla","Meegoda","Narahenpita","Peliyagoda","Thambuttegama","Keppetipola","Nuwara Eliya",
           "Bandarawela","Embilipitiya","Veyangoda","Norochcholai","Kandy"]
PROVENANCE = {"observed", "estimated", "synthetic", "missing"}

KEYS = {
    "core.market_prices_weekly": ["week_start_date", "economic_centre", "crop"],
    "core.market_arrivals_weekly": ["week_start_date", "economic_centre", "crop"],
    "core.supply_season": ["season", "district", "crop"],
    "core.planting_target_season": ["season", "district", "crop"],
    "core.cost_season": ["season", "crop"],
    "core.national_supply_season": ["season", "crop"],
    "core.weather_daily": ["date", "district"],
    "outputs.c1_glut_season": ["season", "economic_centre", "crop"],
    "outputs.c2_pressure_score": ["season", "district", "crop"],
    "outputs.c3_training_label": ["season", "district", "crop"],
    "outputs.c3_risk_prediction": ["season", "district", "crop"],
}

class ValidationError(ValueError):
    pass

def validate(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Fail loudly on broken keys, unknown names or unknown provenance values."""
    errs = []
    keys = KEYS.get(table, [])
    missing_cols = [k for k in keys if k not in df.columns]
    if missing_cols:
        errs.append(f"missing key columns {missing_cols}")
    else:
        if keys and df.duplicated(keys).any():
            errs.append(f"{int(df.duplicated(keys).sum())} duplicate keys")
        if keys and df[keys].isna().any().any():
            errs.append("null values in key columns")
    for col, allowed in [("crop", CROPS), ("district", DISTRICTS), ("economic_centre", CENTRES)]:
        if col in df.columns:
            bad = set(df[col].dropna()) - set(allowed)
            if bad:
                errs.append(f"unknown {col} values: {sorted(bad)[:5]}")
    if "provenance" in df.columns:
        bad = set(df["provenance"].dropna()) - PROVENANCE
        if bad:
            errs.append(f"unknown provenance values: {bad}")
    if errs:
        raise ValidationError(f"{table}: " + "; ".join(errs))
    return df
