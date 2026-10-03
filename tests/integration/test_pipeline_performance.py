"""
Performance and Benchmark Integration Tests for AnnotationOps v2 Enterprise Scale.
Validates:
- Database query execution time
- Data loading performance
- KPI engine calculation speed

Note: Uses the CI-generated dataset (500 assets, 600 annotations).
      Thresholds are scaled accordingly; full 5K/25K benchmarks run locally.
"""

import time
import pytest
from pathlib import Path
from pipeline.database import DEFAULT_DB_PATH
from pipeline.metrics import (
    compute_operations_kpis,
    compute_quality_kpis,
    compute_annotator_kpis,
    compute_backlog_reconciliation,
    compute_trend_kpis,
)
from app.dashboard.app import load_warehouse_data


@pytest.fixture(autouse=True)
def require_db():
    """Skip performance tests if the warehouse DB hasn't been generated."""
    if not DEFAULT_DB_PATH.exists():
        pytest.skip("Warehouse DB not found — run scripts/run_pipeline.py first")


def test_warehouse_data_loading_performance():
    """Loading all core tables from warehouse into pandas must complete in under 5 seconds."""
    t0 = time.perf_counter()
    tasks_df, annotations_df, gold_df, rejections_df, annotators_df = load_warehouse_data(str(DEFAULT_DB_PATH))
    elapsed = time.perf_counter() - t0

    assert len(tasks_df) >= 100, f"Expected at least 100 tasks, got {len(tasks_df)}"
    assert len(annotations_df) >= 50, f"Expected at least 50 annotations, got {len(annotations_df)}"
    assert elapsed < 5.0, f"Data loading took {elapsed:.2f}s, expected < 5.0s"


def test_kpi_engine_calculation_performance():
    """All major metric computation engines must execute combined in under 10 seconds."""
    t0 = time.perf_counter()
    ops = compute_operations_kpis(DEFAULT_DB_PATH)
    qual = compute_quality_kpis(DEFAULT_DB_PATH)
    ann = compute_annotator_kpis(DEFAULT_DB_PATH)
    recon = compute_backlog_reconciliation(DEFAULT_DB_PATH)
    trends = compute_trend_kpis(DEFAULT_DB_PATH)
    elapsed = time.perf_counter() - t0

    assert ops["total_tasks"] >= 1
    assert isinstance(qual, dict)
    assert len(ann) >= 1
    assert recon["is_reconciled"] is True
    assert len(trends["weekly_trend"]) >= 1

    assert elapsed < 10.0, f"KPI calculations took {elapsed:.2f}s, expected < 10.0s"
