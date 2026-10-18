# DVC walkthrough: committing dataset v1.2 (brand-new database)

v1.2 is a **brand-new database** built from versioned inputs by `scripts/build_db.py`, not an upgrade of the v1.1 file. There are no migrations. Assumes the repository already tracks `data/glut_ews.duckdb.dvc`, `parquet.dvc` and `data/raw/sources.dvc`, with a Google Drive remote named `storage`. **The schema owner does steps 1–5; teammates do step 6.**

## 0. Before you start

```bash
git status                 # must be clean
git checkout main && git pull
dvc pull
dvc status -c              # "Cache and remote 'storage' are in sync"
```
Close every notebook, DuckDB UI or SQL client that has the database open.

## 1. Keep the old version recoverable, then branch

```bash
git tag -a dataset-v1.1 -m "Dataset v1.1: before footprint regeneration and label removal"
git push origin dataset-v1.1
dvc push                   # v1.1 data objects are in the remote
git checkout -b data/v1.2-new-database
```

## 2. Bring in the v1.2 project files

From the unzipped `glut-ews` v1.2 package (adjust the path), copy everything except Git/DVC internals, your environment and the generated database:

macOS / Linux:
```bash
rsync -av --exclude '.git' --exclude '.dvc' --exclude '.venv' --exclude 'data/glut_ews.duckdb' \
      --exclude 'parquet/' --exclude 'data/backups/' ~/Downloads/glut-ews/ ./
rm -f docs/TEAM_GUIDE.md docs/placeholder_realism_report.md docs/placeholder_realism_metrics.json
```
Windows (PowerShell):
```powershell
robocopy $HOME\Downloads\glut-ews . /E /XD .git .dvc .venv parquet data\backups /XF glut_ews.duckdb
Remove-Item docs\TEAM_GUIDE.md, docs\placeholder_realism_report.md, docs\placeholder_realism_metrics.json -ErrorAction SilentlyContinue
```
This brings in the build inputs: `data/raw/extracts/`, the two new CSVs in `data/raw/sources/`, `data/reference/`, `data/config/crop_district_footprint.csv`, `sql/schema.sql`, and the scripts.

## 3. Build the new database

```bash
uv pip install -r requirements.txt && uv pip install -e .
python scripts/build_db.py           # brand-new database (seed 20261018); old file backed up to data/backups/
python scripts/validate_dataset.py   # docs/validation_summary.md
pytest -q                            # 20 passed — includes "fresh build reproduces the committed database"
```
Your `docs/validation_summary.md` must match the one in the package. The data is identical for the same inputs and seed; the `.duckdb` file's bytes and hash may still differ (DuckDB files aren't byte-deterministic), which is why the database is built rather than copied.

## 4. Update DVC tracking and commit

```bash
dvc add data/glut_ews.duckdb parquet data/raw/extracts data/raw/sources
git add -A
git status          # expect: .dvc files (incl. new data/raw/extracts.dvc), sql/schema.sql, data/reference/, data/config/,
                    #         scripts/, src/, tests/, notebooks/, docs/, README.md
                    # NOT expected: data/glut_ews.duckdb, parquet/*.parquet, data/raw/extracts/*.parquet, data/backups/
git commit -m "Dataset v1.2: brand-new database, crop-district footprint, recalibrated prices, no label columns"
dvc push            # data objects FIRST
git push -u origin data/v1.2-new-database
```

## 5. Verify, then merge

```bash
dvc status -c                 # in sync with the remote
dvc diff dataset-v1.1         # what changed in DVC-tracked data vs v1.1
```
Prove v1.1 is still retrievable from the remote alone (separate worktree, empty cache):
```bash
git worktree add ../glut-ews-v1.1 dataset-v1.1
cd ../glut-ews-v1.1 && dvc pull
python -c "import duckdb; c=duckdb.connect('data/glut_ews.duckdb', read_only=True); print(c.sql('select count(*) from core.supply_season').fetchone())"   # (1750,)
cd - && git worktree remove ../glut-ews-v1.1 --force
```
Open a pull request; after review, merge and tag:
```bash
git checkout main && git pull
git tag -a dataset-v1.2 -m "Dataset v1.2" && git push origin dataset-v1.2
```

## 6. Teammates: getting the new version

```bash
git checkout main && git pull
dvc pull
uv pip install -r requirements.txt && uv pip install -e .
pytest -q
```
Re-run your notebooks and check the downstream-impact table in `01_AUDIT_REPORT.md`. Teammates never run `build_db.py` themselves; they pull the schema owner's build. After any `git checkout <branch-or-tag>`, run `dvc checkout`.

## 7. Rolling back

| Situation | Command |
|---|---|
| Look at v1.1 temporarily | `git checkout dataset-v1.1 -- data/glut_ews.duckdb.dvc parquet.dvc && dvc checkout data/glut_ews.duckdb.dvc parquet.dvc` (return: `git checkout HEAD -- data/glut_ews.duckdb.dvc parquet.dvc && dvc checkout`) |
| Undo v1.2 on main after merging | `git revert -m 1 <merge-commit>` → `dvc checkout` → `git push` (teammates: `git pull && dvc pull`) |
| Undo a local build before committing | copy the newest `data/backups/glut_ews_*.duckdb` over `data/glut_ews.duckdb`, or `git checkout -- data/glut_ews.duckdb.dvc && dvc checkout` |

## 8. Pitfalls

| Pitfall | Avoid it by |
|---|---|
| Code pushed before data → teammates' `dvc pull` fails | `dvc push` before `git push`; check `dvc status -c` |
| Forgetting `dvc add` after a build → `.dvc` still points to the old database | Always `dvc add data/glut_ews.duckdb parquet` after `build_db.py` / `rebuild_db.py` |
| Build inputs not tracked → nobody else can rebuild | Track `data/raw/extracts` and `data/raw/sources` with DVC; `data/reference/`, `data/config/`, `sql/` with Git |
| Database open elsewhere during a build or `dvc add` | Close notebooks and SQL clients first |
| Two people building → different binary files and conflicting `.dvc` hashes | Only the schema owner builds; others pull |
| Patching the database by hand | Never: change an input and rebuild (published module outputs are re-applied automatically) |
| Schema-breaking change for consumers | Announce it with the downstream-impact table; tag the dataset version |

## 9. Optional: a `dvc.yaml` pipeline

Because the database is now built from scratch from declared inputs, it can become a DVC pipeline stage, so `dvc repro` rebuilds only when an input changes. To switch from `dvc add`:

```bash
dvc remove data/glut_ews.duckdb.dvc parquet.dvc     # a file can't be both dvc-add tracked and a pipeline output
```
`dvc.yaml`:
```yaml
stages:
  build:
    cmd: python scripts/build_db.py
    deps:
      - data/raw/extracts
      - data/raw/sources
      - data/reference
      - data/config/crop_district_footprint.csv
      - data/outputs
      - sql/schema.sql
      - sql/views.sql
      - scripts/build_db.py
      - scripts/rebuild_db.py
      - src/glut_ews/build
      - src/glut_ews/common
    outs:
      - data/glut_ews.duckdb
      - parquet
  validate:
    cmd: python scripts/validate_dataset.py
    deps: [data/glut_ews.duckdb, scripts/validate_dataset.py]
    outs:
      - docs/validation_summary.md:
          cache: false
```
Then `dvc repro`, `git add dvc.yaml dvc.lock`, commit, `dvc push`, `git push`. Teammates run `dvc pull` as before. Keep in mind that `data/outputs` is a dependency, so a newly published module output triggers a full rebuild, which is the intended behaviour.
