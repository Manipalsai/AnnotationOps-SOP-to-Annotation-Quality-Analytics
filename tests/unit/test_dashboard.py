"""
Smoke tests for dashboard script and metrics integration.
Uses self-contained test DB fixture — no pre-generated files required.
"""

import py_compile
from pathlib import Path
from app.dashboard.app import load_warehouse_data
from pipeline.metrics import (
    compute_operations_kpis,
    compute_quality_kpis,
    compute_annotator_kpis,
    compute_trend_kpis,
)


def test_dashboard_script_compiles():
    """Verify app/dashboard/app.py has valid Python syntax."""
    path = Path("app/dashboard/app.py")
    assert path.exists()
    assert py_compile.compile(str(path), doraise=True) is not None


def test_dashboard_warehouse_data_loading(test_db_path):
    tasks_df, annotations_df, gold_df, rejections_df, annotators_df = load_warehouse_data(str(test_db_path))
    assert len(tasks_df) >= 1
    assert len(annotations_df) >= 0
    assert len(annotators_df) >= 12


def test_dashboard_metrics_data_integrity(test_db_path):
    ops = compute_operations_kpis(test_db_path)
    assert "total_tasks" in ops
    assert "completed_tasks" in ops
    assert "rejection_rate_pct" in ops

    qual = compute_quality_kpis(test_db_path)
    assert "accuracy_pct" in qual
    assert "cohens_kappa" in qual
    assert "confusion_matrix" in qual
    assert len(qual["confusion_matrix"]["labels"]) == 3

    ann = compute_annotator_kpis(test_db_path)
    assert not ann.empty
    assert "gold_accuracy_pct" in ann.columns

    trends = compute_trend_kpis(test_db_path)
    assert "daily_volume" in trends or "weekly_trend" in trends
