"""
Performance and Benchmark Integration Tests for AnnotationOps v2 Enterprise Scale.
Validates:
- Database query execution time under 25,000+ records
- Data loading and caching performance
- Backlog waterfall computation efficiency
"""

import time
from pipeline.database import DEFAULT_DB_PATH
from pipeline.metrics import (
    compute_operations_kpis,
    compute_quality_kpis,
    compute_annotator_kpis,
    compute_backlog_reconciliation,
    compute_trend_kpis,
)
from app.dashboard.app import load_warehouse_data


def test_warehouse_data_loading_performance():
    """Loading all core tables from warehouse into pandas must complete in under 2.5 seconds."""
    t0 = time.perf_counter()
    tasks_df, annotations_df, gold_df, rejections_df, annotators_df = load_warehouse_data(str(DEFAULT_DB_PATH))
    elapsed = time.perf_counter() - t0

    assert len(tasks_df) >= 5000
    assert len(annotations_df) >= 20000
    assert elapsed < 2.5, f"Data loading took {elapsed:.2f}s, expected < 2.5s"


def test_kpi_engine_calculation_performance():
    """All 5 major metric computation engines must execute combined in under 3.0 seconds."""
    t0 = time.perf_counter()
    ops = compute_operations_kpis(DEFAULT_DB_PATH)
    qual = compute_quality_kpis(DEFAULT_DB_PATH)
    ann = compute_annotator_kpis(DEFAULT_DB_PATH)
    recon = compute_backlog_reconciliation(DEFAULT_DB_PATH)
    trends = compute_trend_kpis(DEFAULT_DB_PATH)
    elapsed = time.perf_counter() - t0

    assert ops["total_tasks"] >= 5000
    assert qual["total_gold_evaluated"] >= 400
    assert len(ann) >= 12
    assert recon["is_reconciled"] is True
    assert len(trends["weekly_trend"]) == 12

    assert elapsed < 3.0, f"KPI calculations took {elapsed:.2f}s, expected < 3.0s"
