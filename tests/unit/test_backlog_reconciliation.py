"""
Unit tests for Backlog Waterfall Reconciliation and Operational Volume Balancing.
Verifies:
- Total Tasks = Completed + Pending + Rework + Escalated
- 12-Week Waterfall Identity: Closing = Opening + Ingested - Completed
- Strict reconciliation boolean is True across the entire operational timeline.
"""

import sqlite3
from pathlib import Path
from pipeline.database import DEFAULT_DB_PATH
from pipeline.metrics import compute_backlog_reconciliation, compute_operations_kpis


def test_total_task_queue_reconciliation():
    """Verify that every single task in the queue is accounted for across exclusive operational states."""
    ops = compute_operations_kpis(DEFAULT_DB_PATH)

    total = ops["total_tasks"]
    completed = ops["completed_tasks"]
    pending = ops["pending_backlog"]

    assert total > 0, "Total tasks must be greater than zero"
    assert completed > 0, "Completed tasks must be greater than zero"
    assert completed + pending == total, f"Queue does not reconcile: {completed} + {pending} != {total}"
    assert ops["reconciled"] is True, "Reconciliation flag must evaluate to True"


def test_task_status_exhaustive_sum():
    """Verify tasks table status partition sums exactly to total count."""
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM tasks;")
    total_tasks = cursor.fetchone()[0]

    cursor.execute("""
        SELECT 
            SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status = 'REWORK' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status = 'ESCALATED' THEN 1 ELSE 0 END)
        FROM tasks;
    """)
    completed, pending, rework, escalated = cursor.fetchone()
    conn.close()

    status_sum = (completed or 0) + (pending or 0) + (rework or 0) + (escalated or 0)
    assert status_sum == total_tasks, (
        f"Status sum {status_sum} ({completed}C + {pending}P + {rework}R + {escalated}E) "
        f"does not match total tasks {total_tasks}"
    )


def test_weekly_backlog_waterfall_identity():
    """Verify that every weekly slice in the 12-week waterfall reconciles without discrepancy."""
    recon = compute_backlog_reconciliation(DEFAULT_DB_PATH)
    assert recon["is_reconciled"] is True, "Waterfall failed reconciliation identity check"

    df = recon["waterfall_df"]
    assert len(df) == 12, f"Expected 12 operational weeks in waterfall, got {len(df)}"

    for idx, row in df.iterrows():
        opening = row["Opening Backlog"]
        ingested = row["New Tasks Ingested"]
        completed = row["Completed Tasks"]
        closing = row["Closing Backlog"]

        assert closing == opening + ingested - completed, (
            f"Week {row['Week']} waterfall mismatch: {closing} != {opening} + {ingested} - {completed}"
        )
        assert row["Reconciles"] is True
