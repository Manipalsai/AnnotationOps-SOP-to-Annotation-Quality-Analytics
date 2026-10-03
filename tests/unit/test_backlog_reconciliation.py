"""
Unit tests for Backlog Waterfall Reconciliation.
Uses self-contained test DB fixture — no pre-generated files required.
"""

import sqlite3
from pipeline.metrics import compute_backlog_reconciliation, compute_operations_kpis


def test_total_task_queue_reconciliation(test_db_path):
    ops = compute_operations_kpis(test_db_path)
    total = ops["total_tasks"]
    completed = ops["completed_tasks"]
    pending = ops["pending_backlog"]
    assert total > 0
    assert completed >= 0
    assert completed + pending == total
    assert ops["reconciled"] is True


def test_task_status_exhaustive_sum(test_db_path):
    conn = sqlite3.connect(str(test_db_path))
    total_tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    row = conn.execute("""
        SELECT
            SUM(CASE WHEN status='COMPLETED' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status='PENDING'   THEN 1 ELSE 0 END),
            SUM(CASE WHEN status='REWORK'    THEN 1 ELSE 0 END),
            SUM(CASE WHEN status='ESCALATED' THEN 1 ELSE 0 END)
        FROM tasks
    """).fetchone()
    conn.close()
    status_sum = sum(v or 0 for v in row)
    assert status_sum == total_tasks


def test_weekly_backlog_waterfall_identity(test_db_path):
    recon = compute_backlog_reconciliation(test_db_path)
    assert recon["is_reconciled"] is True
    df = recon["waterfall_df"]
    assert len(df) == 12
    for _, row in df.iterrows():
        expected_closing = row["Opening Backlog"] + row["New Tasks Ingested"] - row["Completed Tasks"]
        assert row["Closing Backlog"] == expected_closing
        assert row["Reconciles"] is True
