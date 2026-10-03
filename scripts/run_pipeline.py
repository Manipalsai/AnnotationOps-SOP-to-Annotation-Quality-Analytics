"""
AnnotationOps End-to-End Orchestrator Pipeline Script.

Executes:
1. Raw export ingestion & multi-stage validation gates (pipeline/validate.py)
2. Rejection routing with standardized error reason codes
3. Relational database loading (pipeline/database.py)
4. Automated SQL data quality & integrity checks (sql/quality_checks.sql)
5. Analytical metrics calculation (pipeline/metrics.py)
6. Executive operational & quality scorecard report

Designed for IDEMPOTENT execution: running repeatedly will not duplicate records.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pipeline.database import DEFAULT_DB_PATH, init_db, load_processed_and_rejected, load_tasks_and_gold
from pipeline.metrics import compute_annotator_kpis, compute_operations_kpis, compute_quality_kpis
from pipeline.validate import process_raw_directory


def run_sql_quality_audit(db_path: Path) -> dict[str, int]:
    """Execute SQL integrity checks and report violation row counts."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Check 1: Duplicate annotations
    cursor.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT task_id, annotator_id FROM annotations GROUP BY task_id, annotator_id HAVING COUNT(*) > 1
        );
        """
    )
    dup_count = cursor.fetchone()[0]

    # Check 2: Null critical fields
    cursor.execute(
        """
        SELECT COUNT(*) FROM annotations
        WHERE task_id IS NULL OR annotator_id IS NULL OR condition IS NULL OR annotation_timestamp IS NULL;
        """
    )
    null_count = cursor.fetchone()[0]

    # Check 3: Invalid condition labels
    cursor.execute(
        """
        SELECT COUNT(*) FROM annotations WHERE condition NOT IN ('NEW', 'OPEN_BOX', 'DAMAGED');
        """
    )
    invalid_label_count = cursor.fetchone()[0]

    # Check 4: Conditional violations
    cursor.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT annotation_id FROM annotations
            WHERE condition = 'NEW' AND (packaging_condition IS NOT NULL OR seal_condition IS NOT NULL OR damage_type IS NOT NULL)
            UNION ALL
            SELECT annotation_id FROM annotations
            WHERE condition = 'OPEN_BOX' AND (packaging_condition IS NULL OR seal_condition IS NULL OR damage_type IS NOT NULL)
            UNION ALL
            SELECT annotation_id FROM annotations
            WHERE condition = 'DAMAGED' AND (damage_type IS NULL OR damage_severity IS NULL OR description IS NULL OR packaging_condition IS NOT NULL)
        );
        """
    )
    conditional_violation_count = cursor.fetchone()[0]

    conn.close()

    return {
        "duplicate_count": dup_count,
        "null_count": null_count,
        "invalid_label_count": invalid_label_count,
        "conditional_violations": conditional_violation_count,
    }


def execute_pipeline(db_path: str | Path = DEFAULT_DB_PATH, verbose: bool = True):
    """Execute full automated data engineering and quality pipeline."""
    db_p = Path(db_path)

    print("================================================================================")
    print("ANNOTATIONOPS: SOP-TO-ANALYTICS PIPELINE EXECUTION")
    print("================================================================================")

    # 1. Validation & Rejection Routing
    print("\n[Step 1/5] Ingesting & Validating Raw Submissions...")
    scanned, clean, rejected = process_raw_directory()
    print(f"  - Scanned Raw Files: {scanned}")
    print(f"  - Validated Clean:   {clean}")
    print(f"  - Rejected Audit:    {rejected}")

    # 2. Database Loading
    print("\n[Step 2/5] Initializing Relational Warehouse & Loading Tables...")
    init_db(db_p)
    tasks_loaded, gold_loaded = load_tasks_and_gold(db_p)
    clean_loaded, rej_loaded = load_processed_and_rejected(db_p)
    print(f"  - Tasks in Queue:        {tasks_loaded}")
    print(f"  - Gold Benchmark Items:  {gold_loaded}")
    print(f"  - Clean Warehouse Rows:  {clean_loaded}")
    print(f"  - Rejection Audit Rows:  {rej_loaded}")

    # 3. SQL Data Quality Checks
    print("\n[Step 3/5] Running Automated SQL Integrity Gates...")
    dq_results = run_sql_quality_audit(db_p)
    all_clean = all(v == 0 for v in dq_results.values())

    for check_name, count in dq_results.items():
        status = "PASSED (0 errors)" if count == 0 else f"FAILED ({count} violations!)"
        print(f"  - {check_name:<25} : {status}")

    if not all_clean:
        print("\n[CRITICAL ERROR] Warehouse failed SQL integrity checks. Pipeline aborted.")
        sys.exit(1)

    # 4. Metric Calculations
    print("\n[Step 4/5] Computing Operations & Quality Science Metrics...")
    ops_kpis = compute_operations_kpis(db_p)
    qual_kpis = compute_quality_kpis(db_p)
    ann_df = compute_annotator_kpis(db_p)

    # 5. Executive Scorecard
    print("\n[Step 5/5] Executive Operations Scorecard Summary:")
    print("--------------------------------------------------------------------------------")
    print(f"  * Total Task Queue       : {ops_kpis['total_tasks']}")
    print(f"  * Completed Tasks        : {ops_kpis['completed_tasks']} ({ops_kpis['completion_rate_pct']}%)")
    print(f"  * Pending Backlog        : {ops_kpis['pending_backlog']}")
    print(f"  * Avg / Median Duration  : {ops_kpis['avg_processing_time_seconds']}s / {ops_kpis['median_processing_time_seconds']}s")
    print(f"  * Pipeline Rejection Rate: {ops_kpis['rejection_rate_pct']}%")
    print(f"  * Gold Set Evaluations   : {qual_kpis['total_gold_evaluated']}")
    print(f"  * Gold Accuracy          : {qual_kpis['accuracy_pct']}% (Target >= 95.0%)")
    print(f"  * Cohen's Kappa (kappa)  : {qual_kpis['cohens_kappa']} (Target >= 0.85)")
    print("--------------------------------------------------------------------------------")

    if verbose and not ann_df.empty:
        print("\nAnnotator Performance Summary:")
        print(ann_df[["annotator_id", "display_name", "tasks_completed", "avg_duration_sec", "rejection_rate_pct", "gold_accuracy_pct"]].to_string(index=False))

    print("\n================================================================================")
    print("PIPELINE COMPLETED SUCCESSFULLY: All validation gates passed.")
    print("================================================================================\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AnnotationOps Pipeline Runner")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="Path to SQLite warehouse")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose tables")
    args = parser.parse_args()

    execute_pipeline(args.db_path, verbose=not args.quiet)
