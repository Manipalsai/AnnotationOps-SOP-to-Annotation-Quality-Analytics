"""
Unit and Smoke Tests for Dashboard and Data Preparation (app/dashboard/app.py).
Verifies:
- Dashboard source code compiles cleanly without syntax errors
- Warehouse loader correctly retrieves all 5 core tables
- All metric aggregation functions feeding dashboard components execute without runtime exceptions
"""

import py_compile
from pathlib import Path
import pytest
from app.dashboard.app import load_warehouse_data
from pipeline.database import DEFAULT_DB_PATH
from pipeline.metrics import (
    compute_operations_kpis,
    compute_quality_kpis,
    compute_annotator_kpis,
    compute_trend_kpis,
)


def test_dashboard_script_compiles():
    """Verify that app/dashboard/app.py has valid Python syntax and compiles cleanly."""
    dashboard_path = Path("app/dashboard/app.py")
    assert dashboard_path.exists()
    compiled_path = py_compile.compile(str(dashboard_path), doraise=True)
    assert compiled_path is not None


def test_dashboard_warehouse_data_loading():
    """Ensure load_warehouse_data retrieves structured dataframes from the warehouse."""
    tasks_df, annotations_df, gold_df, rejections_df, annotators_df = load_warehouse_data(str(DEFAULT_DB_PATH))

    assert len(tasks_df) >= 5000
    assert len(annotations_df) > 0
    assert len(gold_df) >= 400
    assert len(rejections_df) > 0
    assert len(annotators_df) >= 12


def test_dashboard_metrics_data_integrity():
    """Ensure all metrics feeding dashboard pages compute valid structures."""
    ops = compute_operations_kpis(DEFAULT_DB_PATH)
    assert "total_tasks" in ops
    assert "completed_tasks" in ops
    assert "rejection_rate_pct" in ops

    qual = compute_quality_kpis(DEFAULT_DB_PATH)
    assert "accuracy_pct" in qual
    assert "cohens_kappa" in qual
    assert "confusion_matrix" in qual
    assert len(qual["confusion_matrix"]["labels"]) == 3

    ann = compute_annotator_kpis(DEFAULT_DB_PATH)
    assert not ann.empty
    assert "gold_accuracy_pct" in ann.columns
    assert "rejection_rate_pct" in ann.columns

    trends = compute_trend_kpis(DEFAULT_DB_PATH)
    assert "daily_volume" in trends
    assert "daily_quality" in trends
    assert "rejection_summary" in trends
