"""Generation of the modelled tables and v0 module outputs (used by scripts/build_db.py).

Inputs : raw.* and reference core.* tables in the database being built, plus
         data/reference/national_supply_season.csv, national_planting_targets.csv, model_parameters.csv
         and data/config/crop_district_footprint.csv.
Output : DataFrames for the generated core tables and v0 outputs. Fixed seed -> identical results.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SEED = 20261018
CROPS = ["Tomato", "Pumpkin", "Cucumber", "Winged bean", "Green chilli"]
YIELD_BOUNDS = {"Tomato": (8, 30), "Pumpkin": (7, 22), "Cucumber": (7, 22), "Winged bean": (5, 14), "Green chilli": (3, 10)}
DCS_ITEMS = {"Tomatoe - No 1.": "Tomato", "Red Pumpkin": "Pumpkin", "Cucumber": "Cucumber", "Green Chillies": "Green chilli"}
HARTI_ITEMS = {"TOMATOES": "Tomato", "PUMPKIN": "Pumpkin", "CUCUMBER": "Cucumber", "GREEN CHILLIES": "Green chilli"}
WFP_CROPS = {"Tomato": "Tomato", "Pumpkin": "Pumpkin"}          # WFP "Chili" is dried chilli -> not used
WFP_MARKET = {"Dambulla": "Economic Centre-Dambulla", "Meegoda": "Meegoda(DEC)", "Narahenpita": "Colombo City",
              "Thambuttegama": "Thambuttegama", "Keppetipola": "Keppetipola (DEC}", "Nuwara Eliya": "Nuwara Eliya",
              "Bandarawela": "Bandarawela", "Embilipitiya": "Embilipitiya", "Veyangoda": "Gampaha",
              "Norochcholai": "Puttalam", "Kandy": "Kandy"}
WFP_PROXY = {"Narahenpita", "Veyangoda", "Norochcholai"}        # town market used as proxy for the DEC
CANON = {"Nuwaraeliya": "Nuwara Eliya", "N eliya": "Nuwara Eliya", "N'Eliya": "Nuwara Eliya", "Mullativu": "Mullaitivu",
         "Mullathivu": "Mullaitivu", "Kurunagala": "Kurunegala", "Moneragala": "Monaragala", "Rathnapura": "Ratnapura"}
REPORT = {}


def canon_district(x: str) -> str:
    x = re.sub(r"\s+IP$", "", str(x).strip()).replace("Pol onnaruwa", "Polonnaruwa").replace(
        "Monaragal a", "Monaragala").replace("Hasal aka", "Hasalaka")
    x = re.sub(r"\[.*\]", "", x).strip()
    return CANON.get(x, x)


def week_index(d: pd.Series) -> pd.DataFrame:
    d = pd.to_datetime(d)
    return pd.DataFrame({"year": d.dt.year, "week": ((d.dt.dayofyear - 1) // 7 + 1).clip(upper=52)})


def ar1(n: int, phi: float, sd: float, rng) -> np.ndarray:
    e, out = 0.0, np.empty(n)
    for i in range(n):
        e = phi * e + rng.normal(0, sd)
        out[i] = e
    return out


def harvest_month_season(dates: pd.Series) -> pd.Series:
    d = pd.to_datetime(dates)
    return pd.Series(np.where(d.dt.month <= 4, (d.dt.year - 1).astype(str) + "/" + d.dt.year.astype(str).str[2:] + " Maha",
                              d.dt.year.astype(str) + " Yala"), index=dates.index)


# ------------------------------------------------------------------------------------------
def load(con, ref_dir: Path):
    q = lambda s: con.sql(s).df()
    return {
        "season": q("SELECT * FROM core.dim_season ORDER BY season_start"),
        "cal": q("SELECT * FROM core.dim_calendar ORDER BY week_start_date"),
        "district": q("SELECT * FROM core.dim_district ORDER BY district"),
        "centre": q("SELECT * FROM core.dim_economic_centre ORDER BY economic_centre"),
        "bridge": q("SELECT * FROM core.bridge_district_centre ORDER BY district, economic_centre"),
        "cost": q("SELECT * FROM core.cost_season ORDER BY crop, season"),
        "macro": q("SELECT * FROM core.macro_monthly ORDER BY month"),
        "national": pd.read_csv(ref_dir / "national_supply_season.csv"),
        "nat_targets": pd.read_csv(ref_dir / "national_planting_targets.csv"),
        "params": pd.read_csv(ref_dir / "model_parameters.csv"),
        "cf": q("SELECT * FROM raw.cf_district_tables ORDER BY ALL"),
        "cf_wb": q("SELECT * FROM raw.cf_national_winged_bean ORDER BY ALL"),
        "harti": q("SELECT * FROM raw.harti_weekly_prices ORDER BY ALL"),
        "agstat_prices": q("SELECT * FROM raw.agstat_annual_prices ORDER BY ALL"),
        "wfp": q("SELECT * FROM raw.wfp_market_prices ORDER BY ALL"),
        "dcs": q("SELECT * FROM raw.dcs_weekly_retail_prices"),
        "weather_raw": q("SELECT location_id, date, temperature_2m_mean_c, temperature_2m_max_c, precipitation_sum_mm, "
                         "et0_fao_evapotranspiration_mm FROM raw.weather_daily ORDER BY location_id, strptime(date, '%m/%d/%Y')"),
        "locations": q("SELECT * FROM raw.weather_locations ORDER BY location_id"),
    }


# ------------------------------------------------------------------------------------------
def build_weather(D, rng):
    loc = D["locations"].assign(district=lambda x: x.city_name.map(canon_district))
    loc = loc[loc.district.isin(D["district"].district)]
    w = D["weather_raw"].merge(loc[["location_id", "district"]], on="location_id")
    w["date"] = pd.to_datetime(w.date, format="%m/%d/%Y")
    w = w.rename(columns={"temperature_2m_mean_c": "temp_mean_c", "temperature_2m_max_c": "temp_max_c",
                          "precipitation_sum_mm": "rainfall_mm", "et0_fao_evapotranspiration_mm": "et0_mm"})
    w = w[["date", "district", "rainfall_mm", "temp_mean_c", "temp_max_c", "et0_mm"]]
    last = w.date.max()
    obs = w[w.date >= "2018-07-01"]
    days = pd.date_range(last + pd.Timedelta(days=1), "2025-12-31")
    syn = []
    for d, g in w.groupby("district"):
        g = g.set_index("date")
        analog = {y: int(rng.integers(2014, 2024)) for y in sorted(set(days.year))}
        for day in days:
            src = day.replace(year=analog[day.year]) if not (day.month == 2 and day.day == 29) else day.replace(
                year=analog[day.year], day=28)
            r = g.loc[src]
            rain = r.rainfall_mm * np.exp(rng.normal(0, 0.30)) if r.rainfall_mm > 0 else 0.0
            tm = r.temp_mean_c + rng.normal(0, 0.35)
            syn.append((day, d, round(rain, 1), round(tm, 1), round(max(r.temp_max_c + rng.normal(0, 0.45), tm + 1.0), 1),
                        round(max(r.et0_mm * rng.normal(1, 0.06), 0.1), 2)))
    syn = pd.DataFrame(syn, columns=obs.columns)
    out = pd.concat([obs, syn], ignore_index=True).sort_values(["date", "district"])
    REPORT["weather_daily"] = {"observed_rows": len(obs), "modelled_rows": len(syn),
                               "modelled_period": f"{days.min().date()} to {days.max().date()}"}
    out["date"] = out.date.dt.date
    return out


def season_weather(weather, seasons):
    w = weather.assign(date=pd.to_datetime(weather.date))
    rows = []
    for _, s in seasons.iterrows():
        a, b = pd.Timestamp(s.season_start), pd.Timestamp(s.season_end)
        x = w[(w.date >= a) & (w.date <= b)].groupby("district").agg(
            rain=("rainfall_mm", "sum"), heavy=("rainfall_mm", lambda v: (v >= 50).sum()))
        x["season"] = s.season
        rows.append(x.reset_index())
    sw = pd.concat(rows)
    sw["rain_z"] = sw.groupby("district").rain.transform(lambda v: (v - v.mean()) / v.std())
    return sw


# ------------------------------------------------------------------------------------------
def cf_tables(D):
    cf = D["cf"].copy()
    cf["district"] = cf.district_raw.map(canon_district)
    cf["rk"] = cf.report_year * 100 + cf.report_month
    cf = cf[cf.rk == cf.groupby(["season", "crop"]).rk.transform("max")]
    g = cf.groupby(["season", "crop", "district"])[["target_ha", "cultivated_ha", "expected_production_t"]].sum().reset_index()
    g["share"] = g.cultivated_ha / g.groupby(["season", "crop"]).cultivated_ha.transform("sum")
    g["yr"] = np.where(g.cultivated_ha > 5, g.expected_production_t / g.cultivated_ha, np.nan)
    lo = g.crop.map(lambda c: YIELD_BOUNDS[c][0] * 0.5)
    g.loc[g.yr < lo, "yr"] = np.nan                       # extraction artefacts (production = 1 x area)
    return g


def build_national(D, rng):
    n = D["national"].copy()
    wb = D["cf_wb"].dropna(subset=["expected_production_t"])
    obs = {}
    for _, r in wb.iterrows():
        s = r.season.split(" (")[0]
        obs[s] = r.expected_production_t / r.cultivated_ha
    m = n.crop == "Winged bean"
    ys = []
    for s in n.loc[m, "season"]:
        ys.append(obs.get(s, 10.15 * (0.97 if s.endswith("Yala") else 1.0) * np.exp(rng.normal(0, 0.04))))
    n.loc[m, "yield_t_ha"] = np.round(ys, 2)
    n.loc[m, "production_t"] = np.round(n.loc[m, "extent_ha"] * n.loc[m, "yield_t_ha"], 1)
    REPORT["national_supply_season"] = {"winged_bean_yield_from_DOA_crop_forecast": sorted(obs),
                                        "winged_bean_yield_modelled_seasons": int(m.sum() - len(obs))}
    return n


def build_supply(D, foot, national, sweather, cfg, rng):
    seasons = list(D["season"].season)
    nat = national.set_index(["crop", "season"])
    sw = sweather.set_index(["district", "season"])
    yf = cfg.groupby(["crop", "district"]).yr.median().reset_index()
    yf["yfac"] = (yf.yr / yf.groupby("crop").yr.transform("median")).clip(0.7, 1.45)
    yf = yf.set_index(["crop", "district"]).yfac
    rows, src = [], {"cf_share_seasons": 0, "modelled_share_seasons": 0}
    for crop in CROPS:
        fd = foot[foot.crop == crop].district.tolist()
        cfc = cfg[cfg.crop == crop]
        cf_seasons = set(cfc.season)
        for s in seasons:
            st = s[-4:]
            same = cfc[cfc.season.str.endswith(st)]
            base = (same if len(same) else cfc).groupby("district").share.mean()
            for d in fd:
                if s in cf_seasons:
                    x = cfc[(cfc.season == s) & (cfc.district == d)]
                    share = float(x.share.iloc[0]) if len(x) else 0.0
                    src["cf_share_seasons"] += 1
                else:
                    share = float(base.get(d, 0.0)) * np.exp(rng.normal(0, 0.15))
                    src["modelled_share_seasons"] += 1
                ext = nat.loc[(crop, s), "extent_ha"] * share
                if ext < 1.0:
                    continue                               # not cultivated that season -> no row
                hv, rz = (sw.loc[(d, s), "heavy"], sw.loc[(d, s), "rain_z"]) if (d, s) in sw.index else (0, 0)
                wf = np.exp(-0.02 * (hv - 3) + 0.02 * np.clip(rz, -2, 2))
                y = nat.loc[(crop, s), "yield_t_ha"] * yf.get((crop, d), 1.0) * wf * np.exp(rng.normal(0, 0.06))
                lo, hi = YIELD_BOUNDS[crop]
                if y > hi:
                    y = hi - rng.uniform(0.3, 0.12 * (hi - lo))      # soft cap: no pile-up at the bound
                y = float(max(y, lo + rng.uniform(0.2, 0.8)) if y < lo else y)
                rows.append((s, d, crop, round(ext, 1), round(ext * y, 1), round(y, 2)))
    out = pd.DataFrame(rows, columns=["season", "district", "crop", "extent_ha", "production_t", "yield_t_ha"])
    REPORT["supply_season"] = {**src, "rows": len(out)}
    return out


def build_targets(D, supply, cfg, rng):
    nt = D["nat_targets"].set_index(["season", "crop"]).target_ha
    ratio = (nt / D["national"].set_index(["season", "crop"]).extent_ha).rename("r")
    obs = cfg.set_index(["season", "crop", "district"]).target_ha
    rows, n_obs = [], 0
    for _, r in supply.iterrows():
        t = obs.get((r.season, r.crop, r.district), np.nan)
        if pd.notna(t) and t > 0:
            n_obs += 1
        else:
            t = r.extent_ha * float(ratio.get((r.season, r.crop), 1.2)) * np.exp(rng.normal(0, 0.08))
        rows.append((r.season, r.district, r.crop, round(max(t, 0.8 * r.extent_ha), 1)))
    REPORT["planting_target_season"] = {"from_DOA_crop_forecast": n_obs, "modelled": len(rows) - n_obs}
    return pd.DataFrame(rows, columns=["season", "district", "crop", "target_ha"])


# ------------------------------------------------------------------------------------------
def colombo_prices(D, rng):
    cal = D["cal"][["week_start_date", "year", "week"]].copy()
    h = D["harti"].copy()
    h["crop"] = h.item_name.map(HARTI_ITEMS)
    h = h.dropna(subset=["crop"])
    h["week"] = h.week_label.str[1:].astype(int).clip(upper=52)
    h = h[h.year <= 2025].groupby(["year", "week", "crop", "price_type"]).price_rs_kg.mean().unstack("price_type").reset_index()
    dcs = D["dcs"].copy()
    dcs["Item"] = dcs["Item"].astype(str).str.strip()
    dcs["crop"] = dcs.Item.map(DCS_ITEMS)
    dcs = dcs.dropna(subset=["crop"])
    dcs["p"] = pd.to_numeric(dcs["Avg Price (Rs.)"].astype(str).str.replace(",", ""), errors="coerce")
    mth = pd.to_datetime(dcs.Week.str[:7] + "-01")
    k = dcs.Week.str.extract(r"W(\d)")[0].astype(int)
    dcs["date"] = mth + pd.to_timedelta(7 * (k - 1) + 3, unit="D")
    dcs = pd.concat([dcs, week_index(dcs.date).set_index(dcs.index)], axis=1)
    dcs = dcs.groupby(["year", "week", "crop"]).p.mean().rename("dcs").reset_index()
    out, rep = [], {}
    for crop in [c for c in CROPS if c != "Winged bean"]:
        g = cal.merge(h[h.crop == crop], on=["year", "week"], how="left").merge(
            dcs[dcs.crop == crop][["year", "week", "dcs"]], on=["year", "week"], how="left")
        g["crop"] = crop
        ratio_dcs = np.nanmedian(g.dcs / g.retail)
        wr = (g.wholesale / g.retail).rolling(27, center=True, min_periods=6).median().ffill().bfill()
        src_r = np.where(g.retail.notna(), "observed", "").astype(object)
        src_w = np.where(g.wholesale.notna(), "observed", "").astype(object)
        fill_r = g.retail.isna() & g.dcs.notna()
        g.loc[fill_r, "retail"] = g.loc[fill_r, "dcs"] / ratio_dcs
        src_r = np.where(fill_r, "derived_dcs", src_r).astype(object)
        fill_w = g.wholesale.isna() & g.retail.notna()
        g.loc[fill_w, "wholesale"] = g.loc[fill_w, "retail"] * wr[fill_w]
        src_w = np.where(fill_w, "derived_dcs_ratio", src_w).astype(object)
        for col, srcarr in [("wholesale", src_w), ("retail", src_r)]:
            before = g[col].isna()
            g[col] = np.exp(np.log(g[col]).interpolate(limit=4, limit_direction="both"))
            srcarr[before & g[col].notna()] = "interpolated"
            if col == "wholesale":
                src_w = srcarr
            else:
                src_r = srcarr
        rep[crop] = {"dcs_to_harti_retail_ratio": round(float(ratio_dcs), 3),
                     "wholesale": pd.Series(src_w).value_counts().to_dict(),
                     "retail": pd.Series(src_r).value_counts().to_dict()}
        out.append(g[["week_start_date", "year", "week", "crop", "wholesale", "retail"]])
    col = pd.concat(out)
    # winged bean: modelled from AgStat annual farm-gate prices and the observed low-country seasonal profile
    ap = D["agstat_prices"]
    wbfg = ap[ap.crop_name == "Winged bean"].set_index("year").farmgate_rs_kg.to_dict()
    cufg = ap[ap.crop_name.str.startswith("Cucumber")].set_index("year").farmgate_rs_kg.to_dict()
    cu = col[col.crop == "Cucumber"]
    cu_ann = cu.groupby("year").wholesale.mean()
    k_w = np.median([cu_ann[y] / cufg[y] for y in cufg if y in cu_ann.index])
    wbfg[2025] = wbfg[2024] * cu_ann[2025] / cu_ann[2024]
    lc = col[col.crop.isin(["Cucumber", "Pumpkin"])].copy()
    lc["lp"] = np.log(lc.wholesale)
    lc["dev"] = lc.lp - lc.groupby(["crop", "year"]).lp.transform("mean")
    prof = lc.groupby("week").dev.mean()
    cu_wr = (cu.wholesale / cu.retail).median()
    wb = cal.copy()
    wb["crop"] = "Winged bean"
    noise = ar1(len(wb), 0.6, 0.07, rng)
    wb["wholesale"] = [wbfg[y] * k_w * np.exp(prof[w] * 1.1 + e) for y, w, e in zip(wb.year, wb.week, noise)]
    wb["retail"] = wb.wholesale / cu_wr * np.exp(ar1(len(wb), 0.5, 0.03, rng))
    rep["Winged bean"] = {"wholesale": {"modelled": len(wb)}, "retail": {"modelled": len(wb)}}
    REPORT["colombo_price_sources"] = rep
    return pd.concat([col, wb[col.columns]], ignore_index=True)


def centre_ratios(D, cal):
    w = D["wfp"].copy()
    w["date"] = pd.to_datetime(w.date)
    w["month"] = w.date.dt.to_period("M")
    ret = w[(w.pricetype == "Retail") & (w.unit == "KG") & w.commodity.isin(WFP_CROPS)]
    ref = ret[ret.market == "Colombo City"].groupby(["commodity", "month"]).price.mean().rename("ref")
    months = pd.period_range("2019-01", "2025-12", freq="M")
    lr, mu_tab = {}, []
    for cen, mkt in WFP_MARKET.items():
        x = ret[ret.market == mkt].groupby(["commodity", "month"]).price.mean().to_frame().join(ref, how="inner")
        x["l"] = np.log(x.price / x.ref)
        pooled = float(x.l.mean()) if len(x) else 0.0
        for crop in CROPS:
            if crop in WFP_CROPS and len(x.xs(crop, level=0, drop_level=True) if crop in x.index.get_level_values(0) else []) >= 3:
                xc = x.xs(crop, level=0).l
                mu = float(xc.mean())
                s = pd.Series(np.nan, index=months)
                s[xc.index] = xc.values
                s = s.interpolate(limit_area="inside")
                s = mu + 0.8 * (s.fillna(mu) - mu)
                basis = "WFP observed months (interpolated between, 80% of deviation from market-crop mean kept)"
                n = len(xc)
            else:
                mu = pooled
                s = pd.Series(mu, index=months)
                basis = "WFP market-level mean of tomato and pumpkin ratios (no crop-specific WFP data)"
                n = 0
            lr[(cen, crop)] = s
            mu_tab.append({"economic_centre": cen, "crop": crop, "wfp_market": mkt, "proxy_market": cen in WFP_PROXY,
                           "mean_retail_ratio": round(float(np.exp(mu)), 3), "wfp_months": n, "basis": basis})
    # producing-area means (crop-specific data only) for fallback and wholesale anchoring
    ctype = D["centre"].set_index("economic_centre").centre_type
    prod = [t for t in mu_tab if ctype[t["economic_centre"]].startswith("Producing") and t["wfp_months"] > 0]
    lbar = float(np.mean([np.log(t["mean_retail_ratio"]) for t in prod])) if prod else np.log(0.85)
    for t in mu_tab:                                   # markets with no overlapping WFP months at all
        if t["wfp_months"] == 0 and t["mean_retail_ratio"] == 1.0 and ctype[t["economic_centre"]].startswith("Producing"):
            lr[(t["economic_centre"], t["crop"])] = pd.Series(lbar, index=months)
            t["mean_retail_ratio"] = round(float(np.exp(lbar)), 3)
            t["basis"] = "no overlapping WFP months; producing-area market mean"
    # wholesale: producing-area DECs anchored on WFP Dambulla vs Pettah wholesale (2020-21)
    wh = w[(w.pricetype == "Wholesale") & w.commodity.isin(WFP_CROPS)]
    dam = wh[wh.market == "Economic Centre-Dambulla"].groupby(["commodity", "month"]).price.mean()
    pet = wh[wh.market == "Economic Centre-Pettah"].groupby(["commodity", "month"]).price.mean()
    j = pd.concat([dam.rename("d"), pet.rename("p")], axis=1).dropna()
    dam_w = float(np.exp(np.log(j.d / j.p).mean())) if len(j) else 0.85
    lw = {}
    for (cen, crop), s in lr.items():
        if ctype[cen].startswith("Producing"):
            lw[(cen, crop)] = (np.log(dam_w) + (s - lbar)).clip(upper=np.log(0.95))
        else:
            lw[(cen, crop)] = s.clip(np.log(0.9), np.log(1.1))
    REPORT["centre_price_ratios"] = {"dambulla_wholesale_vs_pettah_wfp": round(dam_w, 3),
                                     "dambulla_pettah_wholesale_month_pairs": len(j),
                                     "producing_area_mean_retail_ratio": round(float(np.exp(lbar)), 3),
                                     "mean_wholesale_ratio": {f"{k[0]}|{k[1]}": round(float(np.exp(v.mean())), 3) for k, v in lw.items()},
                                     "table": mu_tab}
    k_prod = lw
    return lr, k_prod


def traded_combos(D, foot, centres):
    wfp = D["wfp"]
    br = D["bridge"]
    keep = {}
    for _, c in centres.iterrows():
        cen = c.economic_centre
        for crop in CROPS:
            if c.centre_type.startswith("Consumer"):
                keep[(cen, crop)] = "consumer-area market (receives supply from all regions)"
                continue
            fd = set(foot[foot.crop == crop].district)
            sup = br[(br.economic_centre == cen) & br.district.isin(fd) & (br.weight >= 0.05)]
            mkt = WFP_MARKET.get(cen)
            n_wfp = wfp[(wfp.market == mkt) & (wfp.commodity == WFP_CROPS.get(crop, "-"))].date.nunique() if (
                mkt and cen not in WFP_PROXY) else 0
            if len(sup):
                keep[(cen, crop)] = "supplied by footprint district(s): " + ", ".join(sorted(sup.district))
            elif n_wfp >= 5:
                keep[(cen, crop)] = f"WFP reports {crop.lower()} prices at this market ({n_wfp} months)"
    return keep


def build_prices(D, col, lr, k_prod, keep, rng):
    cal = D["cal"][["week_start_date"]].copy()
    cal["month"] = pd.to_datetime(cal.week_start_date).dt.to_period("M")
    rows = []
    for (cen, crop), why in sorted(keep.items()):
        c0 = col[col.crop == crop].set_index("week_start_date").reindex(cal.week_start_date)
        if cen == "Peliyagoda":
            ws, rt = c0.wholesale.values, c0.retail.values
        else:
            l = lr[(cen, crop)].reindex(cal.month).values
            lwv = k_prod[(cen, crop)].reindex(cal.month).values
            ws = c0.wholesale.values * np.exp(lwv) * np.exp(ar1(len(cal), 0.6, 0.065, rng))
            rt = c0.retail.values * np.exp(l) * np.exp(ar1(len(cal), 0.5, 0.05, rng))
        rt = np.maximum(rt, ws * 1.10)
        rows.append(pd.DataFrame({"week_start_date": cal.week_start_date, "economic_centre": cen, "crop": crop,
                                  "wholesale_price_rs_kg": np.round(ws, 2), "retail_price_rs_kg": np.round(rt, 2)}))
    out = pd.concat(rows).dropna(subset=["wholesale_price_rs_kg", "retail_price_rs_kg"])
    REPORT["market_prices_weekly"] = {"rows": len(out), "combinations": len(keep),
                                      "combination_basis": {f"{k[0]}|{k[1]}": v for k, v in sorted(keep.items())}}
    return out


# ------------------------------------------------------------------------------------------
def build_harvest(D, national):
    p = D["params"]
    pget = lambda name, crop: p[(p.parameter == name) & (p.crop == crop)].value.iloc[0]
    curves = {st: np.array([float(v) for v in pget(f"cumulative_planting_progress_{st}", "All").split(",")]) for st in
              ["Maha", "Yala"]}
    cal = D["cal"][["week_start_date", "year", "week"]]
    idx = {(y, w): i for i, (y, w) in enumerate(zip(cal.year, cal.week))}
    seas = D["season"].set_index("season")
    rows = []
    for crop in CROPS:
        lag, dur = [int(v) for v in pget("weeks_to_first_harvest|harvest_duration_weeks", crop).split("|")]
        loss = float(pget("post_harvest_loss_rate", crop))
        prof = np.sin(np.pi * (np.arange(dur) + 0.5) / dur)
        prof /= prof.sum()
        h = np.zeros(len(cal))
        for _, r in national[national.crop == crop].iterrows():
            if r.season not in seas.index:
                continue
            f = np.diff(np.r_[0, curves[r.season[-4:]]])
            s0 = pd.Timestamp(seas.loc[r.season, "season_start"])
            for m in range(6):
                for pw in range(4):
                    plant = s0 + pd.DateOffset(months=m) + pd.Timedelta(days=7 * pw + 3)
                    for k in range(dur):
                        hd = plant + pd.Timedelta(weeks=lag + k)
                        key = (hd.year, min((hd.dayofyear - 1) // 7 + 1, 52))
                        if key in idx:
                            h[idx[key]] += r.production_t * f[m] / 4 * prof[k]
        rows.append(pd.DataFrame({"week_start_date": cal.week_start_date, "crop": crop, "harvest_t": np.round(h, 1),
                                  "farm_transport_loss_t": np.round(h * loss * 0.75, 1)}))
    return pd.concat(rows)


def build_arrivals(D, harvest, supply, national, weather, keep, rng):
    p = D["params"]
    loss = {c: float(p[(p.parameter == "post_harvest_loss_rate") & (p.crop == c)].value.iloc[0]) for c in CROPS}
    br = D["bridge"].pivot_table(index="district", columns="economic_centre", values="weight").fillna(0)
    natp = national.set_index(["crop", "season"]).production_t
    sh = supply.assign(s=lambda x: x.production_t / [natp[(c, s)] for c, s in zip(x.crop, x.season)])
    w = weather.assign(date=pd.to_datetime(weather.date))
    w = pd.concat([w, week_index(w.date).set_index(w.index)], axis=1)
    wk = w.groupby(["district", "year", "week"]).rainfall_mm.sum().reset_index()
    wk["z"] = wk.groupby(["district", "week"]).rainfall_mm.transform(lambda v: (v - v.mean()) / (v.std() + 1e-6))
    zx = wk.pivot_table(index=["year", "week"], columns="district", values="z").fillna(0)
    cal = D["cal"][["week_start_date", "year", "week"]].copy()
    cal["hseason"] = harvest_month_season(cal.week_start_date)
    rows = []
    for crop in CROPS:
        hv = harvest[harvest.crop == crop].set_index("week_start_date").harvest_t.reindex(cal.week_start_date).values
        shc = sh[sh.crop == crop].pivot_table(index="season", columns="district", values="s").fillna(0)
        lm = loss[crop] * 0.25 / (1 - loss[crop] * 0.75)
        for cen in br.columns:
            if (cen, crop) not in keep:
                continue
            wts = np.array([(shc.loc[s].reindex(br.index).fillna(0).values * br[cen].values) if s in shc.index
                            else np.zeros(len(br)) for s in cal.hseason])
            share = wts.sum(1)
            if share.sum() == 0:
                continue
            wn = wts / np.where(share > 0, share, 1)[:, None]
            z = (zx.reindex(list(zip(cal.year, cal.week))).reindex(columns=br.index).fillna(0).values * wn).sum(1)
            arr = hv * (1 - loss[crop] * 0.75) * 0.60 * share * np.exp(-0.06 * np.clip(z - 1, 0, None) + ar1(len(cal), 0.5, 0.08, rng))
            ai = arr / pd.Series(arr).rolling(53, center=True, min_periods=20).mean().replace(0, np.nan).values
            ai = np.nan_to_num(ai, nan=1.0)
            wst = arr * np.clip(lm * np.sqrt(ai), lm * 0.5, lm * 2)
            df = pd.DataFrame({"week_start_date": cal.week_start_date, "economic_centre": cen, "crop": crop,
                               "arrivals_t": np.round(arr, 1), "wastage_t": np.round(wst, 1)})
            rows.append(df[df.arrivals_t > 0])
    out = pd.concat(rows)
    REPORT["market_arrivals_weekly"] = {"rows": len(out), "combinations": out.groupby(["economic_centre", "crop"]).ngroups}
    return out


# ------------------------------------------------------------------------------------------
def build_v0_outputs(D, supply, targets, prices, arrivals, national, weather, rng):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import f1_score
    seasons = list(D["season"].season)
    si = {s: i for i, s in enumerate(seasons)}
    cal = D["cal"][["week_start_date", "week", "harvest_of_season"]].copy()
    cc = D["macro"].set_index("month").ccpi_2021_100
    mp = prices.merge(cal, on="week_start_date")
    mp["real"] = mp.wholesale_price_rs_kg / pd.to_datetime(mp.week_start_date).dt.strftime("%Y-%m").map(cc) * 100
    parts = []
    for _, x in mp.groupby(["crop", "economic_centre"]):
        x = x.sort_values("week_start_date").copy()
        x["ratio"] = x.real / x.real.rolling(53, center=True, min_periods=27).median()
        parts.append(x)
    mp = pd.concat(parts)
    mp["r2"] = mp.ratio / mp.groupby(["crop", "economic_centre", "week"]).ratio.transform("median")
    mp["gw"] = (mp.r2 < 0.70).astype(float).where(mp.r2.notna())
    g = mp[mp.harvest_of_season.isin(seasons)].groupby(["harvest_of_season", "economic_centre", "crop"]).agg(
        glut_weeks=("gw", "sum"), weeks_observed=("gw", "count"), hp=("real", "mean")).reset_index().rename(
        columns={"harvest_of_season": "season"})
    g["si"] = g.season.map(si)
    g = g.sort_values(["crop", "economic_centre", "si"])
    g["historical_glut_label"] = np.where(g.glut_weeks >= 4, "Glut", "No glut")
    gg = g.groupby(["crop", "economic_centre"])
    g["cobweb_index"] = np.log(gg.hp.shift(1) / gg.hp.transform(lambda v: v.shift(2).rolling(3, min_periods=1).mean())).round(4).fillna(0.0)
    g["glut_weeks"] = g.glut_weeks.astype(int)
    g["weeks_observed"] = g.weeks_observed.astype(int)
    g["source_version"] = "v0"
    c1 = g[["season", "economic_centre", "crop", "glut_weeks", "historical_glut_label", "cobweb_index", "weeks_observed", "source_version"]]

    main = D["bridge"].sort_values("weight", ascending=False).drop_duplicates("district").set_index("district").economic_centre
    S = supply.merge(targets, on=["season", "district", "crop"]).merge(D["cost"][["season", "crop", "farmgate_rs_kg", "unit_cost_rs_kg"]], on=["season", "crop"])
    S["economic_centre"] = S.district.map(main)
    S = S.merge(c1[["season", "economic_centre", "crop", "glut_weeks", "historical_glut_label", "cobweb_index"]],
                on=["season", "economic_centre", "crop"], how="left")
    ars = arrivals.merge(cal, on="week_start_date").groupby(["harvest_of_season", "economic_centre", "crop"]).arrivals_t.sum().rename("arr").reset_index().rename(columns={"harvest_of_season": "season"})
    S = S.merge(ars, on=["season", "economic_centre", "crop"], how="left")
    sw = season_weather(weather, D["season"]).rename(columns={"rain_z": "pz"})
    S = S.merge(sw[["season", "district", "pz"]], on=["season", "district"], how="left")
    S["si"] = S.season.map(si)
    S = S.sort_values(["crop", "district", "si"]).reset_index(drop=True)

    def prior_same(t, col):
        v, ix = t[col].values, t.si.values
        out = []
        for i in range(len(v)):
            prev = [v[j] for j in range(i) if ix[j] < ix[i] and (ix[i] - ix[j]) % 2 == 0][-3:]
            out.append(np.mean(prev) if prev else np.nan)
        return pd.Series(out, index=t.index)
    S["avg3"] = S.groupby(["crop", "district"], group_keys=False).apply(lambda t: prior_same(t, "extent_ha"))
    S["pavg3"] = S.groupby(["crop", "district"], group_keys=False).apply(lambda t: prior_same(t, "production_t"))
    grp = S.groupby(["crop", "district"])
    S["lag_margin"] = (S.farmgate_rs_kg / S.unit_cost_rs_kg).groupby([S.crop, S.district]).shift(1)
    S["lag_arr"] = grp.arr.transform(lambda v: v.shift(1) / v.shift(1).rolling(4, min_periods=1).mean())
    S["lag_gs"] = grp.glut_weeks.transform(lambda v: v.shift(1).expanding().mean())
    I = pd.DataFrame({"I1": S.cobweb_index, "I2": S.target_ha / S.avg3, "I3": grp.extent_ha.shift(1) / S.avg3, "I4": S.lag_margin,
                      "I5": S.lag_arr, "I6": S.pz, "I7": S.lag_gs}).replace([np.inf, -np.inf], np.nan)
    for k in I:
        I[k] = I[k].fillna(I.groupby(S.crop)[k].transform("median")).fillna(I[k].median())
        I[k] = I[k].clip(I[k].quantile(0.02), I[k].quantile(0.98))
    N = (I - I.min()) / (I.max() - I.min())
    M = N.values + 1e-9
    pm = M / M.sum(0)
    e = -(pm * np.log(pm)).sum(0) / np.log(len(M))
    wts = (1 - e) / (1 - e).sum()
    S["supply_pressure_score"] = np.round(100 * N.values @ wts, 2)
    q50, q80 = np.percentile(S.supply_pressure_score, [50, 80])
    S["pressure_class"] = np.where(S.supply_pressure_score >= q80, "High", np.where(S.supply_pressure_score >= q50, "Medium", "Low"))
    names = ["price incentive", "planting target", "area momentum", "past profitability", "recent arrivals", "pre-season rainfall", "glut-prone season"]
    contrib = (N.values - N.values.mean(0)) * wts
    S["top_drivers"] = [", ".join(names[j] for j in np.argsort(-r)[:3]) for r in contrib]
    c2 = S[["season", "district", "crop", "supply_pressure_score", "pressure_class", "top_drivers"]].assign(source_version="v0")

    S["gs"] = S.glut_weeks.fillna(0) / 16
    S["surge"] = np.where(S.pavg3 > 0, S.production_t / S.pavg3, 1.0).clip(0.5, 2.0)
    z = lambda v: (v - np.nanmean(v)) / np.nanstd(v)
    lat0 = 0.55 * z(S.gs.values) + 0.45 * z(S.surge.values)
    S["prev_glut"] = S.groupby(["crop", "district"]).historical_glut_label.shift(1).eq("Glut").astype(int)
    S["crop_code"] = S.crop.astype("category").cat.codes
    S["stype"] = S.season.str.endswith("Yala").astype(int)
    split = D["season"].set_index("season").split
    S["split"] = S.season.map(split)
    feat = ["supply_pressure_score", "cobweb_index", "prev_glut", "pz", "crop_code", "stype"]

    def label(lat):
        q55, q85 = np.percentile(lat, [55, 85])
        return np.where(lat >= q85, 2, np.where(lat >= q55, 1, 0))

    def score(y):
        tr, te = (S.si >= 2) & (S.split != "test"), S.split == "test"
        X = S[feat].fillna(0)
        m = HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05, random_state=0, class_weight="balanced").fit(X[tr], y[tr])
        return f1_score(y[te], m.predict(X[te]), average="macro")
    tune = []
    for sd in [0.0, 0.4, 0.7, 1.0]:
        y = label(lat0 + rng.normal(0, sd, len(S)) * np.std(lat0))
        tune.append((sd, round(score(y), 3), y))
    sd, f1, y = min(tune, key=lambda t: abs(t[1] - 0.52))
    lab = np.array(["Low", "Medium", "High"])
    c3l = S[["season", "district", "crop"]].assign(glut_risk_label=lab[y], source_version="v0")
    pred = y.copy()
    flip = rng.random(len(y)) > 0.62
    pred[flip] = np.clip(y[flip] + np.where(rng.random(len(y)) < 0.5, -1, 1)[flip], 0, 2)
    probs = np.array([rng.dirichlet(np.where(np.arange(3) == k, 6.0, np.where(abs(np.arange(3) - k) == 1, 2.5, 1.0))) for k in pred])
    c3p = S[["season", "district", "crop"]].assign(predicted_risk_label=lab[probs.argmax(1)], prob_low=probs[:, 0].round(3),
                                                   prob_medium=probs[:, 1].round(3), prob_high=None, top_reasons=S.top_drivers.values, source_version="v0")
    c3p["prob_high"] = (1 - c3p.prob_low - c3p.prob_medium).round(3)
    REPORT["v0_outputs"] = {"c1_rows": len(c1), "c1_glut_rate": round(float((c1.historical_glut_label == "Glut").mean()), 3),
                                 "c2_rows": len(c2), "entropy_weights": dict(zip(names, np.round(wts, 3).tolist())),
                                 "c3_noise_tuning": [(t[0], t[1]) for t in tune], "c3_chosen_noise": sd, "c3_model_macroF1_test": f1,
                                 "c3_label_shares": c3l.glut_risk_label.value_counts(normalize=True).round(3).to_dict()}
    return c1, c2, c3l, c3p


def build_params_issues(D, foot):
    p = D["params"].copy()
    add = [
        ("yield_bounds_t_ha", c, f"{lo}-{hi}", lo, hi, "Plausible district-season yield range; DOA Crop Forecast district yields and AgStat") for c, (lo, hi) in YIELD_BOUNDS.items()]
    add += [("footprint_inclusion_rule", "All", "core list + proposed if DOA mean share >=6.5% & min >=4% over >=5 seasons, or mean >=5% and AgStat 2024 share >=7%",
             None, None, "data/config/crop_district_footprint.csv"),
            ("centre_price_basis", "All", "Colombo (HARTI) series x WFP market/Colombo retail ratio; producing-area DEC wholesale adjusted by WFP Dambulla/Pettah wholesale ratio",
             None, None, "raw.wfp_market_prices; raw.harti_weekly_prices"),
            ("colombo_gap_fill", "All", "missing HARTI retail <- DCS weekly retail / crop DCS:HARTI ratio; missing wholesale <- retail x rolling HARTI wholesale:retail ratio",
             None, None, "raw.dcs_weekly_retail_prices")]
    p = pd.concat([p[~p.parameter.isin([a[0] for a in add])], pd.DataFrame(add, columns=p.columns)], ignore_index=True)
    ki = pd.DataFrame([
        ("KI-01", "raw.harti_weekly_prices", "Missing weeks (2019 W16; 2020 W11-18 COVID lockdown; 2020 W41-52; 2021 W1-2, W21-24, W34)",
         "Filled from DCS weekly retail where available (KI-19); remaining short gaps log-linearly interpolated"),
        ("KI-02", "raw.harti_weekly_prices", "Week 53 present in 2024 wholesale but not retail; HARTI weeks are not ISO weeks",
         "Week 53 averaged into week 52; calendar uses 7-day blocks from 1 Jan (week 52 spans 8-9 days)"),
        ("KI-03", "raw.agstat_dcs_national_seasonal", "Red pumpkin 2024/25 Maha production (9,608.4 t) identical to the capsicum value; implies 2.3 t/ha vs ~11 t/ha normally",
         "Core uses extent x 11.0 t/ha; raw value retained"),
        ("KI-04", "raw.agstat_dcs_national_seasonal", "Bandakka 2025 Yala equals Ash plantain 2025 Maha (32,681.1) in the DCS workbook - copy errors in 2025 provisional data",
         "2025 values treated as provisional"),
        ("KI-05", "raw.agstat_dcs_national_seasonal", "Values revised between AgStat editions (e.g. 2022 tomato annual extent 6,008 ha in AgStat 2023 vs 5,893 ha in AgStat 2024)",
         "Latest edition used per season"),
        ("KI-06", "raw.cf_district_tables", 'District name variants and text-extraction splits: Moneragala, Nuwaraeliya, N eliya, Mullathivu, Kurunagala, "Pol onnaruwa IP", "Hasal aka IP", "Monaragal a IP"',
         "Canonicalised to 25 standard district names; inter-province rows merged into their district"),
        ("KI-07", "raw.cf_district_tables", "Some bulletins are image-only; several reports are partial-season progress, not finals",
         "District shares taken from the latest report per season (6 seasons); other seasons use the mean same-season share with year-to-year variation"),
        ("KI-08", "raw.cf_national_winged_bean", "DOA Crop Forecast winged bean extent (~650-740 ha) far below DCS 3-season averages (~960-1,130 ha) - different methodologies",
         "DOA Crop Forecast figures used"),
        ("KI-09", "raw.cost_of_cultivation", "Yield, cost and profit published per acre", "Unit costs (Rs/kg) carried; per-hectare values derived with 1 ha = 2.471 ac"),
        ("KI-10", "raw.cost_of_cultivation", "2020/21 Maha special issue (COVID) omitted vegetables except green chilli; cucumber and winged bean never surveyed",
         "Tomato and pumpkin interpolated in real terms; cucumber and winged bean modelled (see data sources and methods)"),
        ("KI-11", "raw.weather_locations", '"Kilinochchi[1]" label artefact; "Moneragala" spelling', "Canonicalised"),
        ("KI-12", "raw.weather_daily", "Weather series ends 2024-06-08", "Extended to 2025-12-31 from analog years with day-level perturbation"),
        ("KI-13", "raw.harti_weekly_prices", "No winged bean price series in HARTI or DCS weekly files", "Weekly series modelled from AgStat annual farm-gate prices and the observed low-country seasonal profile"),
        ("KI-14", "-", "No public market-arrivals series for any economic centre", "Arrivals modelled from production, planting progress, crop calendar, loss rates, DEC share and district routing"),
        ("KI-15", "raw.ccpi_anchors", "Only selected official monthly CCPI points available in project files", "Monthly CCPI log-interpolated between anchors; replace with the official DCS series"),
        ("KI-16", "raw.wfp_market_prices", 'WFP commodity "Chili" is dried chilli (r=0.99 with DCS Dried Chillies No 1; r=0.20 with HARTI green chilli)', "Not used for green chilli"),
        ("KI-17", "core.supply_season", f"District rows limited to the crop-district footprint ({len(foot)} pairs); national totals also include minor cultivation in other districts",
         "District values are not rescaled to national totals; footprint districts carry their DOA-reported share"),
        ("KI-18", "raw.wfp_market_prices", "WFP market coverage is sparse (about 15-24 of 67 months per market-crop) and mostly retail; three DECs have no WFP market (proxies: Colombo City, Gampaha, Puttalam)",
         "Used for relative price levels between markets, shrunk towards market means"),
        ("KI-19", "raw.dcs_weekly_retail_prices", "DCS weekly retail runs 5-11% above HARTI Colombo retail (r=0.96-0.99); DCS series ends 2024-09",
         "Level-adjusted by crop-specific median ratio before filling HARTI gaps"),
    ], columns=["issue_id", "table", "issue", "core_handling"])
    return p, ki


# ------------------------------------------------------------------------------------------
def generate(con, seed: int = SEED, exclude_proposed: bool = False, log=print):
    """Return ({core_table: DataFrame}, {output_table: DataFrame}, report) for the database being built."""
    REPORT.clear()
    rng = np.random.default_rng(seed)
    D = load(con, ROOT / "data" / "reference")
    foot = pd.read_csv(ROOT / "data" / "config" / "crop_district_footprint.csv")
    if exclude_proposed:
        foot = foot[foot.status == "core"]
    log("  weather ...")
    weather = build_weather(D, rng)
    sweather = season_weather(weather, D["season"])
    log("  supply ...")
    cfg = cf_tables(D)
    national = build_national(D, rng)
    supply = build_supply(D, foot, national, sweather, cfg, rng)
    targets = build_targets(D, supply, cfg, rng)
    log("  prices ...")
    col = colombo_prices(D, rng)
    lr, lw = centre_ratios(D, D["cal"])
    keep = traded_combos(D, foot, D["centre"])
    prices = build_prices(D, col, lr, lw, keep, rng)
    log("  harvest and arrivals ...")
    harvest = build_harvest(D, national)
    arrivals = build_arrivals(D, harvest, supply, national, weather, keep, rng)
    log("  starting module outputs (v0) ...")
    c1, c2, c3l, c3p = build_v0_outputs(D, supply, targets, prices, arrivals, national, weather, rng)
    params, issues = build_params_issues(D, foot)
    core = {"dim_crop_district": foot[["crop", "district", "status", "justification", "source"]],
            "national_supply_season": national[["season", "crop", "extent_ha", "production_t", "yield_t_ha"]],
            "supply_season": supply, "planting_target_season": targets, "market_prices_weekly": prices,
            "market_arrivals_weekly": arrivals, "harvest_weekly_national": harvest, "weather_daily": weather,
            "model_parameters": params, "known_issues": issues}
    outputs = {"c1_glut_season": c1, "c2_pressure_score": c2, "c3_training_label": c3l, "c3_risk_prediction": c3p}
    REPORT.update({"seed": seed, "footprint_pairs": len(foot), "proposed_included": not exclude_proposed})
    return core, outputs, dict(REPORT)
