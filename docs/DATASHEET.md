# Datasheet – Vegetable Glut EWS Parent Dataset v1.0
(Structure follows Gebru et al., "Datasheets for Datasets", CACM 2021.)

## Motivation
Built for project J26-ISE-306 to develop and evaluate a four-component pre-planting glut early-warning system for Sri Lankan vegetables: (1) historical glut detection and cobweb analysis, (2) supply pressure scoring, (3) glut risk classification, (4) district cultivation advisory. Integrated multi-source data at consistent keys did not previously exist.

## Composition
- Entities: 5 crops × 25 districts × 12 economic centres; 14 seasons (2018/19 Maha – 2025 Yala); 364 weeks (2019–2025); daily weather 2018-07 – 2025-12.
- Core tables: weekly market prices and arrivals per centre and crop; seasonal district extent, production, planting targets; seasonal national supply; seasonal cost of cultivation and farm-gate prices; daily district weather; monthly CCPI; district→centre routing weights; model parameters; known-issues register.
- No personal or farmer-identifiable data. All data aggregated at district, market or national level.
- Provenance: every core fact row is labelled observed / estimated / synthetic / missing (see README for counts).
- Synthetic components exist because no public series is available: centre-level market arrivals and wastage (none published), wholesale/retail prices at centres other than Colombo, weekly winged bean prices, district shares for seasons without DOA district tables, weather after 2024-06-08.

## Collection process
- HARTI weekly Colombo wholesale/retail prices (2019–2026 file provided by HARTI).
- DOA Socio Economics & Planning Centre: AgStat 2019–2025; Crop Forecast bulletins Feb-2022 – Jul-2026 (district targets, cultivated extent, expected production); Cost of Cultivation reports 2019 Yala – 2025 Yala; Crop Enterprise Budget 2020.
- DCS/DOA socio-economic statistics workbooks (seasonal extent, production, cost).
- Daily weather: Open-Meteo historical export for district coordinates.
- Parameters from literature: HARTI Research Report 247 (2021) – >60% of vegetables marketed via economic centres, district→Dambulla shares; JAS-SL 16(3) 2021 and Gunarathna et al. (MERCon 2020) – ~75% of post-harvest loss before market; NIPHM crop loss figures (2023); COPA/National Audit Office (2015) 30–40% post-harvest loss range.
- Source files and SHA-256 fingerprints: data/raw/source_manifest.csv.

## Synthetic generation methods (summary)
- Weekly national harvest: DCS seasonal production × DOA monthly planting progress × crop calendar (weeks to first harvest, harvest duration).
- Arrivals at a centre: harvest × (1 − 0.75 × loss rate) × 0.60 (DEC share) × district production shares × routing weights × weather shock (producer-weighted heavy-rain anomaly) × AR(1) noise. Market wastage rises with the square root of relative arrivals (consistent with the Dambulla post-harvest loss index study, Tropical Agricultural Research 35(3), 2024). Arrivals are never derived from prices.
- Centre prices: observed Colombo series × centre price factor × AR(1) noise × small local-supply effect; NULL wherever the Colombo series is NULL.
- Winged bean prices: AgStat annual farm-gate prices × cucumber wholesale/farm-gate ratio × low-country seasonal profile × AR(1) noise, with HARTI collection gaps applied.
- District shares (non-bulletin seasons): mean DOA bulletin share × lognormal noise (σ = 0.18), renormalised; district production rescaled to DCS national totals.
- Weather after 2024-06-08: analog-year block bootstrap from 2014–2023.
- Random seeds fixed; generation is reproducible from the build scripts.

## Preprocessing in core
Canonical names (e.g. Moneragala→Monaragala, "Pol onnaruwa IP"→Polonnaruwa), inter-province rows merged into districts, per-acre to per-kg/per-hectare, HARTI week 53 folded into week 52, latest AgStat edition per season, suspect pumpkin 2024/25 Maha production replaced by extent × 11.0 t/ha (raw value retained). No imputation of missing prices in core.

## Uses
Intended: development and evaluation of the four modules; methodological research on glut early warning. Results on synthetic components show pipeline behaviour, not empirical market facts – report observed-subset results alongside. Not intended for operational advisories without replacing synthetic components with real data.

## Distribution
Derived tables may be shared with the research panel and reviewers. Redistribution of original HARTI/DOA/DCS publications should follow the publishers' terms – cite rather than re-host the original documents.

## Maintenance
Owner: project team (parent-schema owner designated by the team). Planned updates: real Dambulla arrivals (RTI request), HARTI multi-market and producer prices, remaining Crop Forecast district tables (image-only bulletins), official monthly CCPI. Each update increments the dataset version (DVC).
