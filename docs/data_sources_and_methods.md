# Data sources and methods

How every table in `data/glut_ews.duckdb` was produced, table by table. This document replaces the former row-level labels: the database no longer carries a per-row source column, so this is where the origin of each part of the data is recorded. Counts come from `docs/generation_report.json` (seed 20261018).

Use it to (a) describe the data honestly in the methodology chapter and (b) build observed-only evaluation subsets (section 4).

## 1. Sources

| Source | Content | Used for |
|---|---|---|
| HARTI weekly price file (Colombo) | Wholesale and retail Rs/kg, 2019–2025, tomato, pumpkin, cucumber, green chilli | Colombo (Peliyagoda) price series |
| DCS weekly retail prices (`dcs_weekly_retail_prices.csv`) | Colombo open-market retail, 2020 – Sep 2024 | Filling HARTI gaps; level-checked against HARTI (r = 0.96–0.99) |
| WFP market price monitoring (`wfp_food_prices_lk.csv`) | Monthly prices at ~39 markets, 2020 – Sep 2025; tomato and pumpkin used ("Chili" is dried chilli – not used) | Relative price levels between markets; Dambulla vs Pettah wholesale |
| DOA Crop Forecast bulletins 2022–2026 | District cultivated extent, targets, expected production | District shares and targets (6 seasons per crop); footprint evidence |
| AgStat 2019–2025, DCS/DOA workbooks | National seasonal extent and production; annual farm-gate prices; 2024 district tables | National supply; winged bean price level; footprint evidence |
| DOA Cost of Cultivation reports | Farm-gate price and unit cost per season | Cost table |
| Open-Meteo export | Daily weather, 25 districts, to 2024-06-08 | Weather |
| HARTI Research Report 247; post-harvest loss literature | DEC share, district→Dambulla routing, loss rates | Arrivals and wastage model parameters |

## 2. Table by table

| Table | From published data | Derived from published data | Modelled (documented method, seeded) |
|---|---|---|---|
| `core.dim_crop_district` | Team field list (core pairs) | Proposed pairs from DOA Crop Forecast / AgStat shares (rule in `data/config/crop_district_footprint.csv`) | — |
| `core.national_supply_season` | All crops except winged bean production | Pumpkin 2024/25 Maha production = extent × 11.0 t/ha (KI-03) | Winged bean: extent from DOA Crop Forecast where reported; yield from DOA expected production in 2021/22 Maha, 2024/25 Maha, 2025 Yala, modelled in 11 seasons |
| `core.supply_season` (402 rows) | — | District extent = DOA district share × national extent in 167 district-seasons | District share for seasons without a DOA table (239 district-seasons): mean same-season DOA share × year-to-year variation; yields: national yield × DOA district yield factor × weather factor × variation |
| `core.planting_target_season` | 163 district targets from DOA Crop Forecast | — | 239: extent × national target/achievement ratio × variation |
| `core.market_prices_weekly` – Peliyagoda (Colombo) | HARTI observed weeks (tomato 336 of 364 wholesale) | DCS-filled weeks (wholesale ~17–20 per crop, retail ~18–21 per crop) | Short interpolations (~8–18 weeks per crop); winged bean entire series (AgStat annual level × observed low-country seasonal profile) |
| `core.market_prices_weekly` – other 11 centres | — | Colombo series × WFP market/Colombo price ratio (tomato, pumpkin: WFP observed months, interpolated); producing-area DEC wholesale anchored on WFP Dambulla/Pettah wholesale ratio 0.837 (15 month pairs) | Cucumber, green chilli, winged bean ratios = market mean of tomato and pumpkin ratios; weekly variation calibrated to WFP ratio variability (CV 8–15%) |
| `core.market_arrivals_weekly` | — | — | All rows: national harvest model × loss rate × DEC share (60%) × footprint district production shares × routing weights × weather shock × variation |
| `core.harvest_weekly_national` | — | — | DCS seasonal production × DOA planting progress curve × crop calendar |
| `core.weather_daily` | 54,250 rows to 2024-06-08 | — | 14,275 rows (2024-06-09 to 2025-12-31): analog-year days with day-level perturbation |
| `core.cost_season` | Seasons with a DOA survey (tomato, pumpkin, green chilli) | Unsurveyed seasons interpolated in real terms | Cucumber and winged bean (never surveyed) |
| `core.macro_monthly` | Official CCPI anchor months | Other months log-interpolated | — |
| `core.bridge_district_centre` | Dambulla shares for 8 districts (HARTI RR-247) | Normalised among the 12 centres | Other routing weights (assumptions) |
| `outputs.*` (v0) | — | — | Generated starting outputs so modules can work in parallel; replaced by module results (v1+) |

## 3. Market coverage decisions

A centre–crop price series exists only where the crop is plausibly traded: consumer-area centres trade all five crops; producing-area centres only where a footprint district supplies them (routing weight ≥ 5%) or WFP reports the crop at that market. Removed combinations: Bandarawela – winged bean; Keppetipola – cucumber, green chilli, winged bean; Norochcholai – tomato, winged bean. Arrival rows exist only where footprint districts supply the centre.

## 4. Observed-only evaluation subsets

Report results on these alongside full-data results:

```sql
-- Colombo prices observed by HARTI (exclude gap weeks listed in KI-01 and winged bean)
SELECT * FROM core.market_prices_weekly
WHERE economic_centre = 'Peliyagoda' AND crop <> 'Winged bean'
  AND week_start_date NOT IN (SELECT week_start_date FROM core.dim_calendar
                              WHERE (year = 2019 AND week = 16) OR (year = 2020 AND week BETWEEN 11 AND 18)
                                 OR (year = 2020 AND week >= 41) OR (year = 2021 AND week IN (1,2,21,22,23,24,34)));

-- District supply in seasons with DOA Crop Forecast district tables
SELECT * FROM core.supply_season
WHERE season IN ('2021/22 Maha','2022 Yala','2022/23 Maha','2023 Yala','2024 Yala','2024/25 Maha');

-- Weather observed
SELECT * FROM core.weather_daily WHERE date <= DATE '2024-06-08';
```

## 5. Not verified

- District-level vegetable statistics from the DCS query tool could not be accessed; footprint evidence relies on DOA Crop Forecast tables and AgStat 2024 district figures.
- AgStat "Chilli" district figures may combine green and dried chilli.
- WFP town markets are used as proxies for three DECs (Narahenpita → Colombo City, Veyangoda → Gampaha, Norochcholai → Puttalam).
- The CCPI is interpolated between official anchor months.
