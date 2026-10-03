# AnnotationOps — SOP-to-Annotation Quality Analytics

> **Enterprise-grade annotation operations analytics system** — SOP contract enforcement → multi-stage validation firewall → SQLite warehouse → statistical quality science → live Streamlit executive dashboard.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-FF4B4B?logo=streamlit&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-59%20passing-22c55e?logo=pytest&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Warehouse-003B57?logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-94a3b8)

---

## 📌 What This Project Is

AnnotationOps demonstrates the **full lifecycle** of an enterprise annotation operations system built from scratch:

```
SOP YAML Contract
      ↓
Raw Annotation Submissions (immutable point-in-time JSONs)
      ↓
4-Stage Validation Firewall  →  Rejection Audit Sink
      ↓
SQLite Analytics Warehouse (7 relational tables)
      ↓
Metrics Engine (Kappa · F1 · SLA Variance · IAA)
      ↓
Streamlit Executive Dashboard (5 pages · global filters · no hardcoded numbers)
```

> **Disclosure:** All data is **fully synthetic and deterministic** (`seed=42`). No real annotators, products, or proprietary data are included.

---

## 🖥️ Dashboard — 5 Analytical Views

All metrics, KPI cards, charts, and tables respond **dynamically** to 6 global sidebar filters. Zero hardcoded numbers.

| # | Tab | What You See |
|---|-----|-------------|
| 1 | **Operations Overview** | Queue velocity, 12-week backlog waterfall, completion SLAs, task status donut |
| 2 | **Quality Science & Agreement** | Gold accuracy, Cohen's Kappa (κ), Macro F1, confusion matrix, difficulty tier breakdown |
| 3 | **Annotator Performance** | Per-annotator scorecards: cycle time, rejection rate, rework rate, gold accuracy |
| 4 | **Data Quality & Rejections** | Firewall audit log, rejection codes, validation stage failure breakdown |
| 5 | **Operational & Quality Trends** | 12-week throughput, accuracy drift, cycle time evolution, SLA target vs. actual variance |

### Global Sidebar Filters

| Filter | Scope |
|--------|-------|
| Date Range | Narrows all views by annotation timestamp |
| Annotator ID | Multi-select: any subset of the 12-person workforce |
| Product Category | 8 categories (Electronics, Clothing, Home & Garden…) |
| Condition Label | NEW · OPEN_BOX · DAMAGED |
| Task Difficulty | EASY · MEDIUM · HARD |
| Operational Status | COMPLETED · PENDING · REWORK · ESCALATED |

**🔄 Clear / Reset All Filters** button restores full-dataset defaults instantly.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  SYNTHETIC DATA GENERATION (seed=42)                        │
│  5,000 product assets  ·  12-annotator workforce            │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌──────────────────────────┴──────────────────────────────────┐
│  4-STAGE VALIDATION FIREWALL  (pipeline/validate.py)        │
│  Stage 1: Schema & Null Checks                              │
│  Stage 2: Categorical Vocabulary Enforcement                │
│  Stage 3: SOP Conditional Business Rules                    │
│  Stage 4: Anomaly Screening & Time Bounds                   │
│       ↓ PASS                       ↓ FAIL                   │
│  clean_annotations.jsonl    rejection_audit table           │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌──────────────────────────┴──────────────────────────────────┐
│  SQLITE ANALYTICS WAREHOUSE  (data/annotationops.db)        │
│  tasks · annotators · annotations · gold_annotations        │
│  rejection_audit · operational_events · simulation_targets  │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌──────────────────────────┴──────────────────────────────────┐
│  METRICS ENGINE + SQL ANALYTICS LIBRARY                     │
│  Cohen's Kappa · Macro F1 · SLA Variance · IAA              │
└──────────────────────────┬──────────────────────────────────┘
                           ↓
┌──────────────────────────┴──────────────────────────────────┐
│  STREAMLIT EXECUTIVE DASHBOARD  (app/dashboard/app.py)      │
│  5 pages · 6 global filters · dynamic metrics               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 Repository Structure

```
ANNOTATIONOPS/
├── app/
│   ├── dashboard/app.py              # Streamlit 5-page executive dashboard
│   └── annotation/static/index.html  # Annotator workstation UI
├── pipeline/
│   ├── validate.py                   # 4-stage SOP validation firewall
│   ├── validate_spec.py              # YAML schema contract parser
│   ├── database.py                   # SQLite warehouse loader & schema
│   └── metrics.py                    # Kappa · F1 · SLA metrics engine
├── scripts/
│   ├── generate_dataset.py           # Synthetic asset generator (seed=42)
│   ├── simulate_annotations.py       # 12-annotator simulation (25K events)
│   ├── run_pipeline.py               # End-to-end pipeline orchestrator
│   └── backfill.py                   # Historical data backfill utility
├── sql/
│   ├── operational_metrics.sql       # Throughput, backlog, completion KPIs
│   ├── annotator_metrics.sql         # Per-annotator scorecards
│   ├── quality_science.sql           # Accuracy, Kappa, IAA analytics
│   ├── data_quality_audit.sql        # Rejection firewall audit queries
│   └── quality_checks.sql            # Gold benchmark integrity checks
├── tests/
│   ├── unit/                         # 10 unit test modules (49 tests)
│   └── integration/                  # 2 integration test modules (10 tests)
├── docs/
│   ├── ARCHITECTURE.md               # System design, data lineage, Mermaid
│   ├── METRICS.md                    # Math formulations & SLA references
│   ├── DATA_DICTIONARY.md            # Full warehouse schema & field types
│   ├── DATA_GENERATION.md            # Synthetic generation methodology
│   └── TESTING.md                    # Test suite structure & coverage
├── schemas/annotation.yaml           # Machine-enforceable SOP contract v1.0.0
├── .streamlit/config.toml            # Dark theme & server config
├── Dockerfile                        # Production container (python:3.13-slim)
├── requirements.txt                  # Python dependencies
└── pytest.ini                        # Test runner config
```

---

## 📊 Dataset at a Glance

| Entity | Count |
|--------|-------|
| Product catalog assets | **5,000** |
| Simulated annotation events | **~25,000** |
| Validated clean annotations | **~24,983** |
| Firewall-blocked rejections | **~893** |
| Gold benchmark records | **400** |
| Annotator workforce personas | **12** |
| Operational scenario weeks | **12** |
| SLA simulation targets | **5** |

**Annotators:** 12 personas across 4 teams (Alpha, Beta, Delta, Gamma), 3 experience levels (Junior/Mid/Senior), 2 shifts (Morning/Evening).

**Product Categories:** Electronics · Clothing · Home & Garden · Books · Toys · Sports · Health & Beauty · Automotive

---

## 🔒 SOP Contract & Validation Logic

Schema defined in `schemas/annotation.yaml` (v1.0.0). Conditionally enforced per label:

```
NEW        → all secondary fields MUST be null
OPEN_BOX   → packaging_condition + seal_condition required; damage fields forbidden
DAMAGED    → damage_type + damage_severity + description (≥10 chars) required
```

**Hard rejection bounds:** `processing_time_seconds ∈ [0.5s, 1800.0s]`  
**Audit flag:** `< 3.0s` → `WARN_SPEED_ANOMALY_FAST`

---

## 📈 Metrics & SLA Targets

| Metric | Formula | Target |
|--------|---------|--------|
| Completion Rate | Completed / Total × 100 | ≥ 85.0% |
| Pipeline Rejection Rate | Rejected / (Valid + Rejected) × 100 | ≤ 3.0% |
| Avg Cycle Time | Σ duration / N | ≤ 12.0s |
| Gold Benchmark Accuracy | Correct / Gold Evaluated × 100 | ≥ 95.0% |
| Cohen's Kappa (κ) | (Po − Pe) / (1 − Pe) | ≥ 0.85 |
| Macro F1-Score | Mean of per-class F1 scores | — |
| Rework Rate | Rework / Completed × 100 | ≤ 5.0% |
| Escalation Rate | Escalated / Total × 100 | ≤ 3.0% |
| Backlog Invariant | Total = Completed + Pending | ✅ Reconciled |

---

## ⚡ Quick Start

```bash
# 1. Clone
git clone https://github.com/Manipalsai/AnnotationOps-SOP-to-Annotation-Quality-Analytics.git
cd AnnotationOps-SOP-to-Annotation-Quality-Analytics

# 2. Virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Generate dataset + run pipeline (deterministic, seed=42)
python scripts/generate_dataset.py --num-assets 5000 --seed 42
python scripts/simulate_annotations.py --count 25000 --seed 42
python scripts/run_pipeline.py

# 5. Launch dashboard
streamlit run app/dashboard/app.py
```

Open **http://localhost:8501**

---

## 🐳 Docker

```bash
docker build -t annotationops .
docker run -p 8501:8501 annotationops
```

Dataset generation and pipeline run automatically during the Docker build.

---

## 🧪 Tests — 59 Passing

```bash
pytest tests/ -v                          # all 59 tests
pytest tests/ --cov=pipeline              # with coverage
pytest tests/unit/ -v                     # unit only
pytest tests/integration/ -v             # integration only
```

| Module | Tests | What It Covers |
|--------|-------|----------------|
| `test_models.py` | 10 | Pydantic annotation model validation |
| `test_spec_validation.py` | 11 | YAML schema contract & SOP rules |
| `test_dataset_generation.py` | 4 | Deterministic reproducibility |
| `test_metrics.py` | 6 | Kappa, rejection rate, cycle time engine |
| `test_dynamic_filters.py` | 4 | Global filter correctness |
| `test_backlog_reconciliation.py` | 3 | Waterfall identity invariant |
| `test_f1_score.py` | 3 | F1 / precision / recall |
| `test_sla_and_variance.py` | 2 | SLA target vs. actual variance |
| `test_sql_analytics.py` | 1 | SQL analytics execution |
| `test_dashboard.py` | 3 | Dashboard import & render |
| `test_workstation_api.py` | 8 | Annotation API endpoints |
| `test_pipeline_performance.py` | 2 | End-to-end pipeline benchmarks |

---

## 🔧 Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.13 |
| Dashboard | Streamlit 1.32+ |
| Visualisation | Plotly 5.19+ |
| Data Processing | Pandas 2.2+ · NumPy 1.26+ |
| Quality Science | scikit-learn 1.4+ |
| Schema Validation | Pydantic 2.6+ · PyYAML 6.0+ |
| Database | SQLite (`sqlite3`) |
| Testing | pytest 8.0+ · pytest-cov 4.1+ |
| Containerisation | Docker (python:3.13-slim) |
| CI/CD | GitHub Actions |

---

## 📚 Documentation

| Doc | Description |
|-----|-------------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design, Mermaid diagram, data lineage, CI/CD |
| [`docs/METRICS.md`](docs/METRICS.md) | Full math formulations, Cohen's Kappa, F1, SLA reference |
| [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) | All 7 warehouse tables with column types |
| [`docs/DATA_GENERATION.md`](docs/DATA_GENERATION.md) | Synthetic generation & persona design methodology |
| [`docs/TESTING.md`](docs/TESTING.md) | Test suite strategy and coverage guide |
| [`schemas/annotation.yaml`](schemas/annotation.yaml) | SOP contract v1.0.0 |

---

## 📄 License

MIT — see [`LICENSE`](LICENSE)

---

## 👤 Author

**Sai Manikanta** · [@Manipalsai](https://github.com/Manipalsai)

> *Portfolio project demonstrating enterprise data engineering, annotation quality science, operational analytics, and full-stack dashboard development.*
