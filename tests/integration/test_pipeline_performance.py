"""
Performance integration tests using the self-contained test DB fixture.
No pre-generated warehouse files required.
"""

import time
from app.dashboard.app import load_warehouse_data
from pipeline.metrics import (
    compute_operations_kpis,
    compute_quality_kpis,
    compute_annotator_kpis,
    compute_backlog_reconciliation,
    compute_trend_kpis,
)


def test_warehouse_data_loading_performance(test_db_path):
    t0 = time.perf_counter()
    tasks_df, annotations_df, gold_df, rejections_df, annotators_df = load_warehouse_data(str(test_db_path))
    elapsed = time.perf_counter() - t0
    assert len(tasks_df) >= 1
    assert elapsed < 5.0, f"Data loading took {elapsed:.2f}s"


def test_kpi_engine_calculation_performance(test_db_path):
    t0 = time.perf_counter()
    ops = compute_operations_kpis(test_db_path)
    qual = compute_quality_kpis(test_db_path)
    ann = compute_annotator_kpis(test_db_path)
    recon = compute_backlog_reconciliation(test_db_path)
    trends = compute_trend_kpis(test_db_path)
    elapsed = time.perf_counter() - t0

    assert ops["total_tasks"] >= 1
    assert isinstance(qual, dict)
    assert len(ann) >= 1
    assert recon["is_reconciled"] is True
    assert elapsed < 10.0, f"KPI calculations took {elapsed:.2f}s"
