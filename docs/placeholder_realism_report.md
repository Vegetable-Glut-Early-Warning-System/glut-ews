# Placeholder Output Realism Report (placeholder_v0)
Generated 2026-10-17. Placeholder outputs let all four modules work in parallel. Each must be replaced by the real module output (same table, same keys, new `source_version`) and downstream modules re-run.

## C1 – outputs.c1_glut_season (840 rows: season × centre × crop)
| Check | Value | Interpretation |
|---|---|---|
| Glut base rate | 30.6% | Target range 25–35% ✔ |
| Glut rate on observed Colombo prices | 42.9% | Same rule on real HARTI data (4 crops) |
| P(glut \| glut same season last year) | 29.1% | ≈ base rate → little persistence; gluts do not simply repeat |
| Agreement with observed Colombo label | 90.1% | High because centre prices are derived from the Colombo series – limited genuine between-centre variation (limitation) |
| Cobweb index mean / SD | 0.045 / 0.357 | Centred near zero, realistic dispersion |

Rule: real price (÷ CCPI) relative to 53-week rolling median, divided by the median ratio for the same calendar week (removes trend and normal seasonal dip); glut week if < 0.70; season = Glut if ≥ 4 glut weeks in the harvest window.

## C2 – outputs.c2_pressure_score (1750 rows: season × district × crop)
Entropy weights: I1_price_incentive 0.0916, I2_target_ratio 0.0952, I3_extent_momentum 0.0774, I4_lag_profitability 0.1778, I5_lag_arrivals 0.1353, I6_preseason_rain 0.1659, I7_glut_propensity 0.2567

| Check | Value | Interpretation |
|---|---|---|
| Score mean / SD | 37.08 / 9.22 | 0–100 scale |
| Spearman with C3 realised label | 0.187 | Weak positive – informative but not deterministic ✔ |
| AUC (High vs rest) | 0.608 | Modest discrimination – leaves room for C3 to add value ✔ |

## C3 – outputs.c3_training_label (1750 rows)
Latent risk = 0.55·z(centre glut share in harvest window) + 0.45·z(district production ÷ prior 3-season same-type mean) + Gaussian noise; High ≥ 85th pct, Medium ≥ 55th; districts < 5 ha = Low.

Noise tuning (HistGradientBoosting on lagged/pre-season features only; test = 2024/25 Maha – 2025 Yala):

| Relative noise SD | Model macro-F1 | Persistence baseline macro-F1 |
|---|---|---|
| 0.0 | 0.579 | 0.347 |
| 0.4 | 0.578 | 0.334 |
| 0.7 | 0.463 | 0.341 |
| 1.0 | 0.459 | 0.354 |

Chosen noise = 0.7 → model macro-F1 **0.463** vs persistence **0.341**: learnable, not trivially predictable ✔. A placeholder giving near-perfect accuracy would indicate leakage by construction.

Class shares by split: test: High 16%, Low 66%, Medium 18%; train: High 12%, Low 60%, Medium 28%; validation: High 19%, Low 54%, Medium 27%

Same-season-last-year label autocorrelation: -0.083 (slightly negative – consistent with cobweb-type alternation).

## C3 – outputs.c3_risk_prediction (input for C4)
Simulated classifier output: accuracy 68.7%, macro-F1 0.654 vs the realised label, with class probabilities. C4 must consume predictions, never the realised label.

## Replacement protocol
1. Module writes its real output to the same table with `source_version='v1'` (keep v0 rows for comparison).
2. Downstream modules re-run; report metric changes v0 → v1.
3. Error-propagation study: perturb 5/10/20% of C1 labels and measure C3/C4 degradation.
