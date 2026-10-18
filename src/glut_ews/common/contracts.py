"""Output contracts: the agreed shape of every table in the `outputs` schema.

A module's output must match its contract before it can enter the parent dataset.
Change a contract only by team agreement (it affects every downstream module).
"""
from __future__ import annotations

import pandas as pd

from .schema import CENTRES, CROPS, DISTRICTS

LABELS_3 = {"Low", "Medium", "High"}

CONTRACTS: dict[str, dict] = {
    "c1_glut_season": {
        "owner": "C1",
        "keys": ["season", "economic_centre", "crop"],
        "required": {"glut_weeks": "int", "historical_glut_label": "str", "cobweb_index": "float", "source_version": "str"},
        "optional": {"weeks_observed": "int"},
        "allowed": {"historical_glut_label": {"Glut", "No glut"}},
        "ranges": {"glut_weeks": (0, 20)},
    },
    "c2_pressure_score": {
        "owner": "C2",
        "keys": ["season", "district", "crop"],
        "required": {"supply_pressure_score": "float", "pressure_class": "str", "source_version": "str"},
        "optional": {"top_drivers": "str"},
        "allowed": {"pressure_class": LABELS_3},
        "ranges": {"supply_pressure_score": (0, 100)},
    },
    "c3_training_label": {
        "owner": "C3",
        "keys": ["season", "district", "crop"],
        "required": {"glut_risk_label": "str", "source_version": "str"},
        "optional": {},
        "allowed": {"glut_risk_label": LABELS_3},
        "ranges": {},
    },
    "c3_risk_prediction": {
        "owner": "C3",
        "keys": ["season", "district", "crop"],
        "required": {"predicted_risk_label": "str", "prob_low": "float", "prob_medium": "float",
                     "prob_high": "float", "source_version": "str"},
        "optional": {"top_reasons": "str"},
        "allowed": {"predicted_risk_label": LABELS_3},
        "ranges": {"prob_low": (0, 1), "prob_medium": (0, 1), "prob_high": (0, 1)},
        "prob_columns": ["prob_low", "prob_medium", "prob_high"],
    },
    "c4_advisory": {
        "owner": "C4",
        "keys": ["plan_season", "district", "crop"],
        "required": {"recent_avg_extent_ha": "float", "recommended_ha": "float", "change_pct": "float",
                     "action": "str", "source_version": "str"},
        "optional": {"suggested_alternatives": "str", "explanation": "str"},
        "allowed": {"action": {"Reduce", "Maintain", "Expand"}},
        "ranges": {"recommended_ha": (0, None), "recent_avg_extent_ha": (0, None)},
    },
}

_NAME_SETS = {"crop": set(CROPS), "district": set(DISTRICTS), "economic_centre": set(CENTRES)}


def contract_columns(table: str, df: pd.DataFrame | None = None) -> list[str]:
    """Contract column order; optional columns included only if present in df."""
    c = CONTRACTS[table]
    cols = c["keys"] + list(c["required"])
    cols += [o for o in c["optional"] if df is None or o in df.columns]
    return cols


def check_output(df: pd.DataFrame, table: str, seasons: set[str] | None = None) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a module output against its contract."""
    if table not in CONTRACTS:
        return [f"unknown output table '{table}' (expected one of {sorted(CONTRACTS)})"], []
    c, errs, warns = CONTRACTS[table], [], []
    needed = c["keys"] + list(c["required"])
    missing = [x for x in needed if x not in df.columns]
    if missing:
        return [f"missing required columns: {missing}"], []
    extra = [x for x in df.columns if x not in needed and x not in c["optional"]]
    if extra:
        warns.append(f"extra columns will be dropped: {extra}")
    if df.empty:
        errs.append("table is empty")
    if df[c["keys"]].isna().any().any():
        errs.append("null values in key columns")
    dup = int(df.duplicated(c["keys"]).sum())
    if dup:
        errs.append(f"{dup} duplicate key rows")
    for col, allowed in _NAME_SETS.items():
        if col in c["keys"]:
            bad = set(df[col].dropna()) - allowed
            if bad:
                errs.append(f"unknown {col} values: {sorted(bad)[:5]}")
    if seasons is not None and "season" in c["keys"]:
        bad = set(df["season"].dropna()) - seasons
        if bad:
            errs.append(f"unknown season labels: {sorted(bad)[:5]}")
    for col, kind in {**c["required"], **{k: v for k, v in c["optional"].items() if k in df.columns}}.items():
        if kind in ("int", "float"):
            num = pd.to_numeric(df[col], errors="coerce")
            if (num.isna() & df[col].notna()).any():
                errs.append(f"column '{col}' must be numeric")
            elif kind == "int" and ((num.dropna() % 1) != 0).any():
                errs.append(f"column '{col}' must contain whole numbers")
    for col, allowed in c["allowed"].items():
        bad = set(df[col].dropna()) - allowed
        if bad:
            errs.append(f"column '{col}' has invalid values {sorted(bad)[:5]} (allowed: {sorted(allowed)})")
        if df[col].isna().any():
            errs.append(f"column '{col}' has missing values")
    for col, (lo, hi) in c["ranges"].items():
        num = pd.to_numeric(df[col], errors="coerce")
        if lo is not None and (num < lo).any():
            errs.append(f"column '{col}' has values below {lo}")
        if hi is not None and (num > hi).any():
            errs.append(f"column '{col}' has values above {hi}")
    if "prob_columns" in c and all(p in df.columns for p in c["prob_columns"]):
        s = df[c["prob_columns"]].apply(pd.to_numeric, errors="coerce").sum(axis=1)
        if ((s - 1).abs() > 0.02).any():
            errs.append("probability columns must sum to 1 (±0.02) on every row")
    sv = set(df["source_version"].dropna().astype(str))
    if len(sv) != 1:
        errs.append(f"source_version must have exactly one value, found {sorted(sv)}")
    return errs, warns
