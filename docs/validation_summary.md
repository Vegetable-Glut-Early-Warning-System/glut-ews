# Validation summary

Generated from `data/glut_ews.duckdb` by `scripts/validate_dataset.py`.

## 1. Crop-district footprint

| crop | core | proposed | districts |
|---|---|---|---|
| Cucumber | Ampara, Anuradhapura, Hambantota, Kurunegala, Monaragala | Puttalam | 6 |
| Green chilli | Ampara, Anuradhapura, Hambantota, Kurunegala, Monaragala, Puttalam | Jaffna | 7 |
| Pumpkin | Ampara, Anuradhapura, Hambantota, Kurunegala, Monaragala | Puttalam | 6 |
| Tomato | Badulla, Kandy, Matale, Nuwara Eliya | Hambantota | 5 |
| Winged bean | Anuradhapura, Hambantota, Kurunegala, Matale | Ratnapura | 5 |

## 2. Rows per crop and district (core.supply_season, 14 seasons)

| district | Cucumber | Green chilli | Pumpkin | Tomato | Winged bean |
|---|---|---|---|---|---|
| Ampara | 13 | 14 | 13 | — | — |
| Anuradhapura | 14 | 14 | 14 | — | 14 |
| Badulla | — | — | — | 14 | — |
| Hambantota | 14 | 14 | 14 | 14 | 14 |
| Jaffna | — | 14 | — | — | — |
| Kandy | — | — | — | 14 | — |
| Kurunegala | 14 | 13 | 14 | — | 14 |
| Matale | — | — | — | 14 | 14 |
| Monaragala | 14 | 14 | 14 | — | — |
| Nuwara Eliya | — | — | — | 14 | — |
| Puttalam | 14 | 13 | 14 | — | — |
| Ratnapura | — | — | — | — | 14 |

— = no rows (district does not cultivate the crop).

## 3. Extent and production by district (mean per season)

| crop | district | mean_extent_ha | mean_production_t | seasons |
|---|---|---|---|---|
| Cucumber | Hambantota | 180.10 | 2,947 | 14 |
| Cucumber | Puttalam | 176.50 | 2,772 | 14 |
| Cucumber | Monaragala | 140.40 | 2,080 | 14 |
| Cucumber | Kurunegala | 136.40 | 2,004 | 14 |
| Cucumber | Anuradhapura | 114.10 | 1,537 | 14 |
| Cucumber | Ampara | 81.40 | 1,633 | 13 |
| Green chilli | Anuradhapura | 1,046.30 | 7,216 | 14 |
| Green chilli | Puttalam | 480.80 | 3,319 | 13 |
| Green chilli | Monaragala | 418.40 | 2,793 | 14 |
| Green chilli | Jaffna | 392.50 | 3,180 | 14 |
| Green chilli | Kurunegala | 344.10 | 2,382 | 13 |
| Green chilli | Ampara | 327.40 | 2,191 | 14 |
| Green chilli | Hambantota | 243.40 | 1,190 | 14 |
| Pumpkin | Anuradhapura | 1,025.70 | 11,730 | 14 |
| Pumpkin | Monaragala | 665.60 | 7,937 | 14 |
| Pumpkin | Puttalam | 245.60 | 2,527 | 14 |
| Pumpkin | Hambantota | 235.20 | 3,784 | 14 |
| Pumpkin | Kurunegala | 198.10 | 3,214 | 14 |
| Pumpkin | Ampara | 195.30 | 3,341 | 13 |
| Tomato | Badulla | 725.40 | 11,327 | 14 |
| Tomato | Matale | 345 | 7,114 | 14 |
| Tomato | Nuwara Eliya | 333.50 | 6,521 | 14 |
| Tomato | Kandy | 212.90 | 3,782 | 14 |
| Tomato | Hambantota | 183 | 2,937 | 14 |
| Winged bean | Ratnapura | 144.40 | 1,857 | 14 |
| Winged bean | Hambantota | 105.60 | 1,398 | 14 |
| Winged bean | Matale | 91 | 1,220 | 14 |
| Winged bean | Kurunegala | 61.80 | 594 | 14 |
| Winged bean | Anuradhapura | 29.50 | 221 | 14 |

## 4. Yield ranges per crop (t/ha)

| crop | min | median | max | distinct_values | rows | plausible_range | within_range |
|---|---|---|---|---|---|---|---|
| Cucumber | 11.06 | 15.16 | 21.94 | 80 | 83 | 7-22 | True |
| Green chilli | 4.07 | 6.62 | 9.32 | 87 | 96 | 3-10 | True |
| Pumpkin | 8.52 | 13.05 | 21.68 | 80 | 83 | 7-22 | True |
| Tomato | 12 | 17.85 | 26.26 | 68 | 70 | 8-30 | True |
| Winged bean | 6.41 | 12.82 | 13.91 | 66 | 70 | 5-14 | True |

## 5. Seasonality: share of annual extent planted in Maha (footprint districts)

| crop | maha_share |
|---|---|
| Cucumber | 0.54 |
| Green chilli | 0.55 |
| Pumpkin | 0.59 |
| Tomato | 0.53 |
| Winged bean | 0.51 |

## 6. Price ranges (Rs/kg, 2019-2025)

| crop | wholesale_min | wholesale_median | wholesale_max | retail_min | retail_median | retail_max | centres |
|---|---|---|---|---|---|---|---|
| Cucumber | 12 | 57 | 189 | 58 | 146 | 322 | 11 |
| Green chilli | 54 | 214 | 1,645 | 124 | 421 | 2,035 | 11 |
| Pumpkin | 10 | 72 | 286 | 54 | 161 | 431 | 12 |
| Tomato | 16 | 120 | 772 | 60 | 222 | 1,103 | 11 |
| Winged bean | 40 | 135 | 388 | 97 | 329 | 922 | 9 |

### Mean wholesale price relative to Peliyagoda (Colombo)

| economic_centre | Cucumber | Green chilli | Pumpkin | Tomato | Winged bean |
|---|---|---|---|---|---|
| Bandarawela | 0.80 | 0.78 | 0.90 | 0.73 | — |
| Dambulla | 0.84 | 0.84 | 0.84 | 0.85 | 0.83 |
| Embilipitiya | 0.82 | 0.83 | 0.88 | 0.79 | 0.83 |
| Kandy | 0.90 | 0.90 | 0.91 | 0.91 | 0.91 |
| Keppetipola | — | — | 0.86 | 0.70 | — |
| Meegoda | 0.94 | 0.94 | 0.92 | 0.97 | 0.94 |
| Narahenpita | 1.00 | 1.00 | 1.00 | 1.01 | 1.00 |
| Norochcholai | 0.95 | 0.95 | 0.95 | — | — |
| Nuwara Eliya | 0.87 | 0.88 | 0.95 | 0.80 | 0.89 |
| Peliyagoda | 1 | 1 | 1 | 1 | 1 |
| Thambuttegama | 0.75 | 0.76 | 0.79 | 0.72 | 0.77 |
| Veyangoda | 1.05 | 1.04 | 1.02 | 1.05 | 1.04 |

— = crop not traded at that centre (no rows).

## 7. Row counts per table

| schema | table | rows | columns |
|---|---|---|---|
| core | bridge_district_centre | 83 | 3 |
| core | cost_season | 70 | 4 |
| core | dim_calendar | 364 | 8 |
| core | dim_crop | 5 | 3 |
| core | dim_crop_district | 29 | 5 |
| core | dim_district | 25 | 6 |
| core | dim_economic_centre | 12 | 3 |
| core | dim_season | 14 | 8 |
| core | harvest_weekly_national | 1820 | 4 |
| core | known_issues | 19 | 4 |
| core | macro_monthly | 84 | 2 |
| core | market_arrivals_weekly | 14104 | 5 |
| core | market_prices_weekly | 19656 | 5 |
| core | model_parameters | 22 | 6 |
| core | national_supply_season | 70 | 5 |
| core | planting_target_season | 402 | 4 |
| core | supply_season | 402 | 6 |
| core | weather_daily | 68525 | 6 |
| outputs | c1_glut_season | 756 | 8 |
| outputs | c2_pressure_score | 402 | 7 |
| outputs | c3_risk_prediction | 402 | 9 |
| outputs | c3_training_label | 402 | 5 |
| outputs | c4_advisory | 0 | 10 |
| raw | agstat_annual_prices | 40 | 5 |
| raw | agstat_dcs_national_seasonal | 64 | 5 |
| raw | ccpi_anchors | 6 | 2 |
| raw | cf_district_tables | 1828 | 10 |
| raw | cf_national_winged_bean | 6 | 5 |
| raw | cost_of_cultivation | 45 | 11 |
| raw | dcs_weekly_retail_prices | 22449 | 6 |
| raw | harti_rr247_dambulla_share | 8 | 2 |
| raw | harti_weekly_prices | 3360 | 7 |
| raw | weather_daily | 142371 | 21 |
| raw | weather_locations | 27 | 8 |
| raw | wfp_market_prices | 11672 | 16 |

## 8. Integrity checks

| Check | Violations |
|---|---|
| Supply rows outside the footprint | 0 |
| Target rows outside the footprint | 0 |
| C2/C3 output rows outside the footprint | 0 |
| Zero / negative extent, production or yield | 0 |
| Production inconsistent with extent x yield (> 0.05 t/ha) | 0 |
| Wholesale above retail | 0 |
| Null or non-positive prices | 0 |
| Dates outside 2019-01-01 to 2025-12-31 | 0 |
| Arrivals rows without a matching price row | 0 |
| Zero-arrival rows | 0 |
| Columns named provenance / note / synthetic | 0 |

**All checks passed.**
