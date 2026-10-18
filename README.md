# glut-ews — Vegetable Glut Early Warning System for Sri Lankan Farmers

Research project **J26-ISE-306**. A pre-planting decision-support system that tells agricultural officers and farmers which vegetable crops, in which districts, are likely to face a glut, and what to grow instead.

**Crops:** tomato · pumpkin · cucumber · winged bean · green chilli
**Coverage:** 2018/19 Maha – 2025 Yala · 25 districts · 12 economic centres

![Architecture](docs/architecture_flowchart.png)

## Components

| | Component | Method | Explainability |
|---|---|---|---|
| C1 | Historical glut detection & cobweb analysis | Anomaly + change-point detection, Nerlove supply response | Interpretable by design |
| C2 | Supply Pressure Score | Entropy-weighted composite index + calibrated score | SHAP + additive contributions |
| C3 | Glut risk classification | XGBoost, temporal validation | SHAP TreeExplainer → plain-language reasons |
| C4 | Displacement-aware cultivation advisory | MOTAD optimisation | Reason codes + binding constraints + what-if |

## Quick start (macOS)

```bash
brew install uv libomp
uv venv --python 3.11 && source .venv/bin/activate
uv pip install -r requirements.txt && uv pip install -e .
dvc pull                 # after the repository has a DVC remote
pytest -q                # 8 passed
```

```python
from glut_ews.common import load
df = load("views.component3_dataset")
```

Starter notebooks: `notebooks/c1_01_eda.ipynb` … `c4_01_eda.ipynb`.

## How data moves

1. Modules read their view from `data/glut_ews.duckdb` (`views.component1_dataset` … `component4_dataset`).
2. A module publishes its result with `publish_output(df, "<table>", version="v1")`, which validates it against its contract and writes it to `data/outputs/`.
3. The schema owner runs `python scripts/rebuild_db.py`: validate → back up → apply → re-apply `sql/views.sql` → integrity checks → re-export `parquet/`.
4. Downstream modules pull and re-run.

## Documentation

| | |
|---|---|
| Team workflow, ownership, rules, per-component guide | [`docs/TEAM_GUIDE.md`](docs/TEAM_GUIDE.md) |
| Dataset layers, provenance, quick reference | [`docs/DATASET_README.md`](docs/DATASET_README.md) |
| Sources, synthetic-data methods, limitations | [`docs/DATASHEET.md`](docs/DATASHEET.md) |
| Column definitions | [`docs/data_dictionary.csv`](docs/data_dictionary.csv) |
| Source defects and how they were handled | [`docs/known_issues.csv`](docs/known_issues.csv) |
| Placeholder output realism checks | [`docs/placeholder_realism_report.md`](docs/placeholder_realism_report.md) |
| Output contracts | [`src/glut_ews/common/contracts.py`](src/glut_ews/common/contracts.py) |

## Data notice

Part of the dataset is synthetic (centre-level arrivals and most centre prices, winged bean prices, some district shares, weather after June 2024) because no public series exists. Every row is labelled `observed`, `estimated`, `synthetic` or `missing`; methods are documented in the datasheet. Report results on the observed subset alongside full-data results.
