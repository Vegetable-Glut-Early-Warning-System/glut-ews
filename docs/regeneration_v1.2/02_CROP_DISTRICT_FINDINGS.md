# Crop–district footprint: research findings

## Method

1. **Team field list** taken as the minimum core set (spelling normalised).
2. **Evidence checked** for every district:
   - **DOA Crop Forecast district tables** (official cultivated extent by district): latest report per season, 6 seasons per crop (2021/22 Maha – 2024/25 Maha; 5 for green chilli). Files: `CF_April_15th_2022` (green chilli: `CF_March_15th_2022`), `CF_July_15th_2022`, `CF_April_15th_2023__Final`, `CF_May_15th_2023_`, `CF_Oct_15th_2024_yala_final` (green chilli: `Crop_forecast15th_September_2024`), `Crop_Forecast_Report_January_Maha_2024-25`. Only text-extractable bulletins could be used; image-only bulletins (e.g. the Maha and Yala finals of 2023/24 and 2025) were not parsed.
   - **AgStat 2025, district tables for 2024** (tomato: Fig 15.2; chilli: Fig 11) — an independent second source for tomato and chilli only.
3. **Rule for proposing an addition** (applied mechanically, no bulk-adding):
   - (A) DOA mean share ≥ 6.5% **and** minimum share ≥ 4% across ≥ 5 seasons; **or**
   - (B) DOA mean share ≥ 5% **and** AgStat 2024 share ≥ 7%.
4. **Rule for dropping a core district:** only if the evidence clearly contradicts it. **No core district was dropped.**

## Final matrix

✔ = core (team list) · ➕ = proposed (included) · blank = not in footprint. Figures: DOA mean share of reported district extent / minimum share over seasons; AgStat 2024 share in brackets where available.

| District | Tomato | Pumpkin | Cucumber | Winged bean | Green chilli |
|---|---|---|---|---|---|
| Anuradhapura | | ✔ 28.7% / 19.1% | ✔ 8.0% / 4.8% | ✔ 4.4% / 1.3% | ✔ 19.0% / 9.7% (15.7%) |
| Ampara | | ✔ 4.5% / 0% | ✔ 5.2% / 0% | | ✔ 5.7% / 2.7% (3.0%) |
| Badulla | ✔ 24.7% / 20.3% (16.0%) | | | | |
| Hambantota | ➕ 6.3% / 3.3% (8.7%) | ✔ 6.6% / 4.5% | ✔ 13.3% / 10.9% | ✔ 16.4% / 12.2% | ✔ 4.4% / 3.2% (5.9%) |
| Jaffna | | | | | ➕ 6.9% / 4.3% (4.7%) |
| Kandy | ✔ 7.0% / 1.9% (8.3%) | | | | |
| Kurunegala | | ✔ 5.3% / 4.0% | ✔ 9.4% / 7.4% | ✔ 9.3% / 3.7% | ✔ 5.4% / 4.7% (6.9%) |
| Matale | ✔ 11.7% / 2.8% (13.5%) | | | ✔ 14.2% / 2.7% | |
| Monaragala | | ✔ 17.7% / 12.3% | ✔ 9.7% / 5.4% | | ✔ 6.3% / 2.3% (7.9%) |
| Nuwara Eliya | ✔ 10.9% / 2.5% (14.3%) | | | | |
| Puttalam | | ➕ 6.7% / 4.5% | ➕ 13.1% / 7.2% | | ✔ 8.2% / 6.3% (10.1%) |
| Ratnapura | | | | ➕ 21.5% / 16.2% | |

## Proposed additions (included, status `proposed`)

| Crop | District | Justification | Source | Rule |
|---|---|---|---|---|
| Tomato | Hambantota | Reported in all 6 DOA seasons; 8.7% of 2024 national tomato extent | DOA Crop Forecast; AgStat 2025 Fig 15.2 (479 of 5,514 ha) | B |
| Pumpkin | Puttalam | Larger DOA share than core districts Hambantota and Kurunegala in every season | DOA Crop Forecast | A |
| Cucumber | Puttalam | Second-largest DOA share in every season (min 7.2%) | DOA Crop Forecast | A |
| Winged bean | Ratnapura | Largest DOA-reported district in every season (min 16.2%) | DOA Crop Forecast | A |
| Green chilli | Jaffna | DOA share above four core districts across 5 seasons | DOA Crop Forecast | A |

To use the team list only: `python scripts/build_db.py --exclude-proposed`, or delete the rows in `data/config/crop_district_footprint.csv`.

## Considered, not added (evidence not strong enough under the rule)

| Crop | District | Evidence | Why not |
|---|---|---|---|
| Tomato | Monaragala | DOA 6.0% / 4.3%; AgStat 4.2% | Below both thresholds |
| Tomato | Anuradhapura | DOA 4.8%; AgStat 8.3% | Below DOA threshold; sources disagree — **worth a field check** |
| Cucumber | Batticaloa | DOA 8.6% mean but 2.3% minimum | Too volatile across seasons |
| Winged bean | Galle | DOA 6.0% / 4.8% | Just below threshold |
| Green chilli | Batticaloa | DOA 8.5% / 7.9% but only 4 seasons | Fewer than 5 seasons; AgStat 2.8% |
| Green chilli | Badulla | DOA 5.9% (4 seasons); AgStat 6.5% | Below both thresholds |

## Core districts with weaker evidence (kept — not clearly contradicted)

- **Pumpkin – Ampara** and **Cucumber – Ampara**: DOA reports zero cultivation in one season each. Those pair-seasons have no row; all other seasons do.
- **Winged bean – Anuradhapura** (4.4%) and **Green chilli – Hambantota** (4.4%): small shares, consistently present.

## Seasonality

District shares are taken season by season from DOA Maha and Yala reports, so each district's Maha/Yala balance follows the reports. National Maha share of extent (footprint districts): 51–59% by crop, consistent with DCS national seasonal totals.

## Could not verify

- **2023 Yala** shares come from `CF_May_15th_2023_`, an early-season progress report (planting to end-April), and **2022 Yala** from `CF_July_15th_2022` (to end-June), so they reflect early planting rather than final extents. Four of six seasons per crop come from finals or near-finals.

- DCS district-level vegetable statistics (query tool not accessible).
- AgStat district "Chilli" may combine green and dried chilli.
- HARTI district producer-price tables were not available in the project files.
- No web source was used to override the DOA evidence; the footprint rests on the DOA and AgStat files listed above.
