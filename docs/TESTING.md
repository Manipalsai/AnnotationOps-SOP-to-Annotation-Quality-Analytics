# Automated Testing Protocol & Quality Assurance Strategy (v2 Enterprise)

**System:** ANNOTATIONOPS  
**Test Framework:** `pytest 8.x / 9.x`  
**Execution Standard:** Zero-Warning Clean Execution  
**Current Suite:** **55 Automated Tests Passing (100% Pass Rate)**  

---

## 1. Testing Philosophy & Zero-Manual-Testing Principle

In enterprise-scale annotation operations, manual visual spot-checking cannot guarantee dataset reliability. 
AnnotationOps enforces automated programmatic validation across all operational tiers:

$$\text{Spec Validation} \longrightarrow \text{Domain Models} \longrightarrow \text{REST API} \longrightarrow \text{Validation Pipeline} \longrightarrow \text{SQL Relational Integrity} \longrightarrow \text{Backlog Reconciliation} \longrightarrow \text{SLA Variance} \longrightarrow \text{Performance Benchmarks}$$

Manual clicking through user interfaces is strictly avoided as proof of correctness; every operational path is verified with deterministic test fixtures.

---

## 2. Test Suite Architecture (55 Automated Tests)

```
tests/
├── unit/
│   ├── test_spec_validation.py        # 11 tests: YAML structural checks, enum validity, broken refs
│   ├── test_models.py                 # 10 tests: Pydantic conditional logic, boundaries, length rules
│   ├── test_dataset_generation.py     #  4 tests: Determinism (seed=42), image integrity, gold schema
│   ├── test_metrics.py                #  6 tests: Cohen's Kappa formulas, chance bounds, confusion matrix
│   ├── test_f1_score.py               #  3 tests: Per-class Precision, Recall, Macro F1, zero-div safeguards
│   ├── test_backlog_reconciliation.py #  3 tests: Queue status identity, 12-week waterfall reconciliation
│   ├── test_sla_and_variance.py       #  2 tests: SLA evaluation rules, variance analysis formatting
│   ├── test_sql_analytics.py          #  1 test:  Executes all 25 queries across 4 SQL files against live DB
│   └── test_dashboard.py              #  3 tests: Syntax compilation, warehouse loading, KPI dataframes
│
└── integration/
    ├── test_workstation_api.py        #  8 tests: REST endpoints, image delivery, raw payload persistence
    ├── test_pipeline.py               #  2 tests: End-to-end ingestion, rejection routing, SQL integrity
    └── test_pipeline_performance.py   #  2 tests: Sub-second DB load and metric calculation benchmarks
```

---

## 3. Test Coverage Breakdown

### 3.1 Backlog Reconciliation & Queue Integrity (`test_backlog_reconciliation.py`)
- Verifies $\text{Total Tasks} = \text{Completed} + \text{Pending Backlog}$.
- Verifies that every task in the queue belongs to exactly one mutually exclusive status (`COMPLETED`, `PENDING`, `REWORK`, `ESCALATED`).
- Verifies that every single week in the 12-week waterfall satisfies $\text{Closing} = \text{Opening} + \text{Ingested} - \text{Completed}$.

### 3.2 Quality Science & F1 Formulations (`test_f1_score.py` & `test_metrics.py`)
- Asserts Cohen's Kappa matches theoretical formula and sklearn implementation.
- Verifies precision, recall, and F1 calculations against ground truth matrices.
- Asserts divide-by-zero protection when edge-case classes receive zero predictions.

### 3.3 SLA Attainment & Variance Analysis (`test_sla_and_variance.py`)
- Tests `MINIMUM` and `MAXIMUM` benchmark evaluation rules.
- Validates absolute variance ($\text{Actual} - \text{Target}$) and percentage variance calculations.
- Asserts structure and types of variance analysis reporting tables.

### 3.4 SQL Analytics Repository Verification (`test_sql_analytics.py`)
- Parses and executes all 25 analytical SQL queries across:
  - `sql/operational_metrics.sql` (Queries 1–10)
  - `sql/annotator_metrics.sql` (Queries 11–15)
  - `sql/quality_science.sql` (Queries 16–22)
  - `sql/data_quality_audit.sql` (Queries 23–25)
- Confirms zero syntax or constraint errors against live SQLite warehouse.

### 3.5 Enterprise Scale Performance Benchmarking (`test_pipeline_performance.py`)
- Validates that loading 5,000 tasks and 25,000+ annotations from SQLite into pandas executes in $< 2.5\text{ seconds}$.
- Validates that computing all 5 major KPI calculation engines executes in $< 3.0\text{ seconds}$.

---

## 4. Running the Complete Automated Test Suite

```bash
# Run complete test suite with verbose output
pytest -v

# Run with test execution duration timing
pytest --durations=10

# Run specific domain test module
pytest tests/unit/test_backlog_reconciliation.py -v
```
