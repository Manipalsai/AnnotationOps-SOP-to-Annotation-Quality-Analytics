# AnnotationOps: SOP-to-Annotation Quality Analytics

Enterprise-grade annotation operations analytics system: SOP contract enforcement -> multi-stage validation firewall -> SQLite warehouse -> statistical quality science -> live Streamlit executive dashboard.

**Live Application:** [https://annotationops-sop-to-annotation-quality-analytics-a6eprw6stkdt.streamlit.app/](https://annotationops-sop-to-annotation-quality-analytics-a6eprw6stkdt.streamlit.app/)

---

## Overview

AnnotationOps demonstrates the full lifecycle of an enterprise human-in-the-loop annotation operations system:

```
SOP YAML Contract (v1.0.0)
      |
Raw Annotation Submissions (immutable point-in-time JSON payloads)
      |
4-Stage Validation Firewall  -->  Rejection Audit Sink
      |
SQLite Analytics Warehouse (7 relational tables)
      |
Metrics Engine (Cohen's Kappa, Macro F1, SLA Variance, Inter-Annotator Agreement)
      |
Streamlit Executive Dashboard (5 analytical views, dynamic global filters)
```

**Disclosure:** All data is fully synthetic and deterministic (`seed=42`). No real annotators, proprietary product records, or confidential business data are included.

---

## Live Dashboard: 5 Analytical Views

All metrics, KPI scorecards, charts, and tables respond dynamically to 6 global sidebar filters with zero hardcoded metrics.

| View | Scope | Description |
|---|---|---|
| 1. Operations Overview | Operational Queue | Throughput velocity, 12-week backlog waterfall, completion SLAs, task status distribution |
| 2. Quality Science & Agreement | Quality Engineering | Gold accuracy, Cohen's Kappa, Macro F1-score, multiclass confusion matrix, difficulty breakdowns |
| 3. Annotator Performance | Workforce Scorecards | Per-annotator metrics: cycle time, validation rejection rate, rework rate, gold accuracy |
| 4. Data Quality & Rejections | Pipeline Audit | Firewall audit trail, rejection reason codes, validation stage failure breakdown |
| 5. Operational & Quality Trends | Longitudinal Analytics | 12-week volume trends, accuracy drift, cycle time evolution, SLA target vs. actual variance |

### Global Sidebar Filters

- **Date Range:** Filters all analytical views by annotation event timestamp.
- **Annotator ID:** Multi-select across the 12-person simulated workforce.
- **Product Category:** 8 categories (Audio, Wearables, Kitchen, Computer Accessories, Home Products, Personal Devices).
- **Condition Label:** Primary conditions (NEW, OPEN_BOX, DAMAGED).
- **Task Difficulty:** Tiers (EASY, MEDIUM, HARD).
- **Operational Status:** Work queue status (COMPLETED, PENDING, REWORK, ESCALATED).
- **Clear All Filters Button:** Instantly resets all global controls back to full-dataset defaults.

---

## Architecture

```
+-------------------------------------------------------------+
|  SYNTHETIC DATA GENERATION (seed=42)                        |
|  5,000 product assets  |  12-annotator workforce            |
+------------------------------+------------------------------+
                               |
                               v
+------------------------------+------------------------------+
|  4-STAGE VALIDATION FIREWALL (pipeline/validate.py)         |
|  Stage 1: Schema & Null Checks                              |
|  Stage 2: Categorical Vocabulary Enforcement                |
|  Stage 3: SOP Conditional Business Rules                    |
|  Stage 4: Anomaly Screening & Time Bounds                   |
|       | PASS                       | FAIL                   |
|  clean_annotations.jsonl    rejection_audit table           |
+------------------------------+------------------------------+
                               |
                               v
+------------------------------+------------------------------+
|  SQLITE ANALYTICS WAREHOUSE (data/annotationops.db)         |
|  tasks | annotators | annotations | gold_annotations        |
|  rejection_audit | operational_events | simulation_targets  |
+------------------------------+------------------------------+
                               |
                               v
+------------------------------+------------------------------+
|  METRICS ENGINE + SQL ANALYTICS LIBRARY                     |
|  Cohen's Kappa | Macro F1 | SLA Variance | IAA              |
+------------------------------+------------------------------+
                               |
                               v
+------------------------------+------------------------------+
|  STREAMLIT EXECUTIVE DASHBOARD (app/dashboard/app.py)       |
|  Self-bootstrapping | 5 views | 6 global filters            |
+-------------------------------------------------------------+
```

---

## Repository Structure

```
ANNOTATIONOPS/
|-- app/
|   |-- dashboard/app.py              # Streamlit 5-view executive dashboard
|   `-- annotation/
|       |-- server.py                 # Annotator workstation HTTP API server
|       `-- static/index.html         # Human annotator labeling UI
|-- pipeline/
|   |-- bootstrap.py                  # Self-bootstrapping engine & warehouse integrity verifier
|   |-- validate.py                   # 4-stage SOP validation firewall
|   |-- validate_spec.py              # YAML schema contract parser & validator
|   |-- database.py                   # SQLite warehouse schema DDL & loaders
|   `-- metrics.py                    # Statistical metrics & SLA calculation engine
|-- scripts/
|   |-- generate_dataset.py           # Deterministic synthetic asset catalog generator (seed=42)
|   |-- simulate_annotations.py       # 12-annotator operational simulation (~25K events)
|   |-- run_pipeline.py               # End-to-end pipeline orchestrator & SQL quality audit
|   `-- backfill.py                   # Historical operational backfill utility
|-- sql/
|   |-- operational_metrics.sql       # Queue velocity, backlog, throughput queries
|   |-- annotator_metrics.sql         # Workforce scorecards & cycle time queries
|   |-- quality_science.sql           # Accuracy, Cohen's Kappa, agreement queries
|   |-- data_quality_audit.sql        # Firewall rejection audit queries
|   `-- quality_checks.sql            # Gold benchmark data integrity assertions
|-- tests/
|   |-- conftest.py                   # Pytest fixtures & automated warehouse setup
|   |-- unit/                         # 10 unit test modules
|   `-- integration/                  # 2 integration test modules
|-- docs/
|   |-- ARCHITECTURE.md               # Detailed system design, data lineage, Mermaid diagrams
|   |-- METRICS.md                    # Mathematical formulations & SLA benchmark reference
|   |-- DATA_DICTIONARY.md            # Warehouse schema, field definitions, index specifications
|   |-- DATA_GENERATION.md            # Synthetic workload generation methodology
|   `-- TESTING.md                    # Test suite execution & coverage guide
|-- schemas/
|   `-- annotation.yaml               # Machine-enforceable SOP specification contract v1.0.0
|-- .github/workflows/
|   `-- ci.yml                        # GitHub Actions automated test & quality gate workflow
|-- .streamlit/
|   `-- config.toml                   # Streamlit production configuration
|-- Dockerfile                        # Multi-stage production container image
|-- requirements.txt                  # Python production dependencies
`-- pytest.ini                        # Pytest configuration
```

---

## Dataset at a Glance

| Entity | Count | Details |
|---|---|---|
| Product Catalog Assets | 5,000 | Unique synthetic items across 8 categories |
| Simulated Annotations | ~25,000 | 12 weeks of historical operations |
| Validated Clean Annotations | ~24,983 | Passed all 4 firewall validation stages |
| Firewall Rejections | ~893 | Trapped with standardized reason codes |
| Gold Benchmark Items | 400 | Ground-truth verification baseline (8% of catalog) |
| Annotator Workforce | 12 | Personas across 4 teams, 3 experience levels, 2 shifts |
| Operational Scenario Weeks | 12 | Historical volume surge, quality dip, protocol change |
| SLA Simulation Targets | 5 | Quantitative operational & quality performance thresholds |

---

## SOP Contract and Validation Logic

Defined in `schemas/annotation.yaml` (v1.0.0). Conditionally enforced per primary condition:

- **NEW:** All secondary fields must be null (packaging, seal, damage type, damage severity, description).
- **OPEN_BOX:** `packaging_condition` and `seal_condition` are mandatory; damage fields must be null.
- **DAMAGED:** `damage_type`, `damage_severity`, and `description` (minimum 10 characters) are mandatory; packaging/seal fields must be null.

**Pacing Bounds:**
- Rejection threshold: `processing_time_seconds` outside `[0.5s, 1800.0s]`.
- Audit warning flag: `processing_time_seconds < 3.0s` marks `WARN_SPEED_ANOMALY_FAST`.

---

## Operational Metrics and SLA Benchmarks

| Metric | Formulation | Target Threshold | Status |
|---|---|---|---|
| Completion Rate | Completed / Total * 100 | >= 85.0% | Meets Target |
| Pipeline Rejection Rate | Rejected / (Valid + Rejected) * 100 | <= 3.0% | Meets Target |
| Average Cycle Time | Sum(duration) / N | <= 12.0s | Meets Target |
| Gold Benchmark Accuracy | Correct / Gold Evaluated * 100 | >= 95.0% | Meets Target |
| Cohen's Kappa | (Po - Pe) / (1 - Pe) | >= 0.85 | Meets Target |
| Macro F1-Score | Unweighted mean of per-class F1 | Monitored | Baseline Established |
| Rework Rate | Rework / Completed * 100 | <= 5.0% | Meets Target |
| Escalation Rate | Escalated / Total * 100 | <= 3.0% | Meets Target |
| Backlog Identity Invariant | Closing = Opening + Ingested - Completed | Reconciled | 100% Invariant Hold |

---

## Quick Start (Local Setup)

### 1. Clone Repository

```bash
git clone https://github.com/Manipalsai/AnnotationOps-SOP-to-Annotation-Quality-Analytics.git
cd AnnotationOps-SOP-to-Annotation-Quality-Analytics
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run Dashboard (Self-Bootstrapping)

```bash
streamlit run app/dashboard/app.py
```

The application automatically verifies the SQLite warehouse on startup. If the database is missing (e.g. on a fresh clone), it executes the deterministic generation pipeline (`seed=42`) and loads the warehouse before displaying the dashboard.

Open: **http://localhost:8501**

---

## Standalone Pipeline Execution

To run the data pipeline manually:

```bash
# 1. Generate synthetic asset catalog and gold baseline
python scripts/generate_dataset.py --num-assets 5000 --seed 42

# 2. Simulate 12-annotator operations and rejection events
python scripts/simulate_annotations.py --count 25000 --seed 42

# 3. Run validation firewall, load SQLite warehouse, and execute SQL audit
python scripts/run_pipeline.py
```

---

## Docker Deployment

```bash
# Build Docker image
docker build -t annotationops .

# Run container
docker run -p 8501:8501 annotationops
```

Dataset generation and warehouse loading are performed during the container build, providing an immediately runnable container.

---

## Automated Testing

The project maintains 59 automated unit and integration tests:

```bash
# Run full test suite
pytest tests/ -v

# Run with test coverage report
pytest tests/ --cov=pipeline

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests only
pytest tests/integration/ -v
```

| Test Module | Tests | Validation Coverage |
|---|---|---|
| `test_models.py` | 10 | Pydantic schema validation & conditional field rules |
| `test_spec_validation.py` | 11 | YAML SOP specification contract parser & constraints |
| `test_dataset_generation.py` | 4 | Deterministic generation reproducibility & schema conformance |
| `test_metrics.py` | 6 | Cohen's Kappa, confusion matrix, cycle time calculations |
| `test_dynamic_filters.py` | 4 | Dynamic multidimensional filter filtering logic |
| `test_backlog_reconciliation.py` | 3 | Backlog waterfall mathematical identity invariants |
| `test_f1_score.py` | 3 | Multiclass precision, recall, and Macro F1 edge cases |
| `test_sla_and_variance.py` | 2 | SLA attainment scoring & operational variance metrics |
| `test_sql_analytics.py` | 1 | Production SQL analytics script syntax & execution |
| `test_dashboard.py` | 3 | Dashboard compilation, warehouse loading, metric integration |
| `test_workstation_api.py` | 8 | REST API endpoints, static assets, and validation submission |
| `test_pipeline_performance.py` | 2 | Warehouse load performance & KPI engine calculation benchmarks |

---

## Technology Stack

- **Runtime:** Python 3.11, 3.12, 3.13
- **Executive Dashboard:** Streamlit 1.32+
- **Visual Analytics:** Plotly 5.19+
- **Data Engineering:** Pandas 2.2+, NumPy 1.26+
- **Quality Science & Statistics:** scikit-learn 1.4+, SciPy 1.12+
- **Schema & SOP Enforcement:** Pydantic 2.6+, PyYAML 6.0+
- **Relational Analytics Warehouse:** SQLite 3
- **Test Engineering:** pytest 8.0+, pytest-cov 4.1+
- **Containerization:** Docker (python:3.13-slim base)
- **CI / CD Quality Gate:** GitHub Actions (matrix testing across Python 3.11, 3.12, 3.13)

---

## Documentation

- [System Architecture](docs/ARCHITECTURE.md): Architecture design, data flow lineage, Mermaid diagrams, and component interactions.
- [Metrics Formulation Guide](docs/METRICS.md): Mathematical formulations for Cohen's Kappa, Macro F1, SLA variance, and backlog identities.
- [Data Dictionary](docs/DATA_DICTIONARY.md): Warehouse schema, column data types, constraints, and index definitions.
- [Synthetic Data Generation Methodology](docs/DATA_GENERATION.md): Persona generation, operational timeline, and scenario milestone modeling.
- [Testing Guide](docs/TESTING.md): Test harness architecture, fixtures, and coverage instructions.
- [SOP Contract](schemas/annotation.yaml): Machine-enforceable SOP specification contract v1.0.0.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

## Author

**Segu Manipal Sai**
- GitHub: [@Manipalsai](https://github.com/Manipalsai)
- Live Application: [Streamlit Community Cloud](https://annotationops-sop-to-annotation-quality-analytics-a6eprw6stkdt.streamlit.app/)
