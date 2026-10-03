# Automated Testing Protocol & Quality Assurance Strategy

**System:** ANNOTATIONOPS  
**Test Framework:** `pytest 8.x`  
**Coverage Engine:** `pytest-cov`  
**Execution Standard:** Zero-Warning Clean Execution  

---

## 1. Testing Philosophy & Zero-Manual-Testing Principle

In mission-critical data operations, human visual spot-checking cannot guarantee dataset integrity. 
AnnotationOps enforces automated programmatic validation across every tier:
$$\text{Specification Validation} \longrightarrow \text{Domain Model Unit Tests} \longrightarrow \text{REST API Integration Tests} \longrightarrow \text{End-to-End Pipeline Tests} \longrightarrow \text{SQL Relational Integrity Audits}$$

Manual clicking through user interfaces is strictly avoided as proof of correctness; every operational path is verified with deterministic test fixtures.

---

## 2. Test Suite Architecture

```
tests/
├── unit/
│   ├── test_spec_validation.py      # 11 tests: YAML structural checks, enum validity, broken refs
│   ├── test_models.py               # 10 tests: Pydantic conditional logic, boundaries, length rules
│   ├── test_dataset_generation.py   #  4 tests: Determinism (seed=42), image integrity, gold schema
│   ├── test_metrics.py              #  6 tests: Cohen's Kappa formulas, chance bounds, confusion matrix
│   └── test_dashboard.py            #  3 tests: Syntax compilation, warehouse loading, KPI dataframes
│
└── integration/
    ├── test_workstation_api.py      #  8 tests: REST endpoints, image delivery, raw payload persistence
    └── test_pipeline.py             #  2 tests: End-to-end ingestion, rejection routing, SQL integrity
```

Total Automated Tests: **44 passing tests**.

---

## 3. Test Coverage Breakdown by Operational Domain

### 3.1 Specification Contract Integrity (`test_spec_validation.py`)
- Asserts `schemas/annotation.yaml` is structurally valid with zero syntax or business errors.
- Verifies rejection of missing top-level keys (`task`, `labels`, `fields`, `conditional_rules`, `metadata_fields`).
- Asserts rejection of duplicate primary labels.
- Validates unsupported field types.
- Verifies broken reference detection when a conditional rule references an undeclared field.
- Asserts rejection if a field is declared as both required and forbidden within the same condition branch.

### 3.2 SOP Conditional Logic (`test_models.py`)
- Asserts valid `NEW` submissions succeed with all secondary attributes as `None`.
- Rejects `NEW` submissions containing packaging or damage fields with `ValueError`.
- Asserts `OPEN_BOX` requires both `packaging_condition` and `seal_condition`.
- Rejects `OPEN_BOX` submissions containing `damage_type` or `description`.
- Asserts `DAMAGED` requires `damage_type`, `damage_severity`, and `description`.
- Enforces minimum 10-character threshold on damage descriptions.
- Asserts processing times must be within physical operating limits ($0.5\text{s} - 1800\text{s}$).

### 3.3 Dataset Engine & Benchmark Baseline (`test_dataset_generation.py`)
- Verifies `data/manifest_tasks.json` (120 tasks) and `data/gold/gold_annotations.json` (30 tasks) exist.
- Validates image dimensions ($600 \times 450$ PNG) and visual header watermarks.
- Validates that all gold records parse through the `GoldRecord` schema with zero errors.
- Asserts strict bitwise determinism: generating twice with `seed=42` produces identical metadata hashes.

### 3.4 Workstation HTTP Server (`test_workstation_api.py`)
- Verifies `GET /` serves HTML workstation interface.
- Verifies `GET /api/tasks` delivers full JSON task queue.
- Verifies `GET /api/spec` returns machine-readable specification contract.
- Verifies `GET /api/images/{filename}` serves PNG image assets securely.
- Asserts `POST /api/annotate` with valid payload creates raw JSON file in `data/raw/` and returns 201.
- Asserts `POST /api/annotate` with invalid conditional payload returns 422 with descriptive error JSON.

### 3.5 End-to-End Ingestion, Validation & SQL Gates (`test_pipeline.py`)
- Ingests test batch with nominal records, missing conditional attributes, and invalid cycle times.
- Asserts nominal records land in `clean_annotations.jsonl` and invalid records land in `rejected_annotations.jsonl` with exact error reason codes (`ERR_CONDITIONAL_FIELD_MISSING`, `ERR_IMPOSSIBLE_TIME`).
- Loads SQLite warehouse and executes automated SQL integrity checks:
  - Asserts duplicate count $= 0$.
  - Asserts null identifier count $= 0$.
  - Asserts invalid label count $= 0$.
  - Asserts SOP conditional logic violations $= 0$.

### 3.6 Quality Science Engine (`test_metrics.py`)
- Tests Cohen's Kappa under perfect agreement ($\kappa = 1.0$), single-class consensus ($\kappa = 1.0$), and chance agreement ($\kappa \le 0.0$).
- Asserts mathematical consistency between vectorized implementation and direct formula.
- Validates confusion matrix cell counts, precision, and recall calculations.

---

## 4. How to Execute Tests Locally

### Run Complete Test Suite
```bash
pytest
```

### Run with Detailed Verbosity
```bash
pytest -v
```

### Run with Code Coverage Report
```bash
pytest --cov=. --cov-report=term-missing
```

### Run Only Integration Tests
```bash
pytest tests/integration/ -v
```

---

## 5. Continuous Integration (GitHub Actions)

Every pull request and commit to `main` executes `.github/workflows/ci.yml` across:
- **Operating Systems**: Ubuntu (`ubuntu-latest`) & Windows (`windows-latest`)
- **Python Versions**: `3.11`, `3.12`, `3.13`
- **Execution Gates**:
  1. Specification contract validation (`pipeline/validate_spec.py`)
  2. Pytest suite execution (`pytest --cov=.`)
  3. End-to-end pipeline idempotency check (`scripts/run_pipeline.py` executed twice)
