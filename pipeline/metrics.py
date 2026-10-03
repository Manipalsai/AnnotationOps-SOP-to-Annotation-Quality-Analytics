"""
Quality Science and Operational Metrics Engine for AnnotationOps.
Calculates statistical agreement metrics (Cohen's Kappa, Inter-Annotator Agreement),
confusion matrices, error rates, throughput velocities, and operational SLAs.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "annotationops.db"
CONDITION_LABELS = ["NEW", "OPEN_BOX", "DAMAGED"]


def calculate_cohens_kappa(y_true: list[str], y_pred: list[str], labels: list[str] = CONDITION_LABELS) -> float:
    """
    Calculate Cohen's Kappa (κ) coefficient between two raters or against gold standard.
    κ = (Po - Pe) / (1 - Pe)
    Returns float in [-1.0, 1.0]. If all labels are identical, returns 1.0.
    """
    if len(y_true) == 0 or len(y_pred) == 0:
        return 0.0

    if len(y_true) != len(y_pred):
        raise ValueError(f"y_true ({len(y_true)}) and y_pred ({len(y_pred)}) must have equal length.")

    # Edge case: perfect agreement on single class
    if len(set(y_true)) == 1 and y_true == y_pred:
        return 1.0

    try:
        kappa = float(cohen_kappa_score(y_true, y_pred, labels=labels))
        return 0.0 if np.isnan(kappa) else round(kappa, 4)
    except Exception:
        # Fallback to direct calculation
        return direct_cohens_kappa(y_true, y_pred, labels)


def direct_cohens_kappa(y_true: list[str], y_pred: list[str], labels: list[str]) -> float:
    """Mathematical reference implementation of Cohen's Kappa."""
    n = len(y_true)
    if n == 0:
        return 0.0

    observed_matches = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    p_o = observed_matches / n

    p_e = 0.0
    for lbl in labels:
        p_true = sum(1 for yt in y_true if yt == lbl) / n
        p_pred = sum(1 for yp in y_pred if yp == lbl) / n
        p_e += (p_true * p_pred)

    if p_e == 1.0:
        return 1.0
    kappa = (p_o - p_e) / (1.0 - p_e)
    return round(float(kappa), 4)


def calculate_confusion_matrix_data(
    y_true: list[str], y_pred: list[str], labels: list[str] = CONDITION_LABELS
) -> dict[str, Any]:
    """
    Compute raw count confusion matrix and per-class precision / recall rates.
    """
    if len(y_true) == 0:
        matrix = [[0] * len(labels) for _ in labels]
        return {"labels": labels, "matrix": matrix, "per_class": {}}

    cm = confusion_matrix(y_true, y_pred, labels=labels)
    cm_list = cm.tolist()

    per_class = {}
    for idx, lbl in enumerate(labels):
        true_pos = cm[idx, idx]
        total_actual = int(cm[idx, :].sum())
        total_pred = int(cm[:, idx].sum())

        recall = round(true_pos / total_actual, 4) if total_actual > 0 else 0.0
        precision = round(true_pos / total_pred, 4) if total_pred > 0 else 0.0

        per_class[lbl] = {
            "actual_count": total_actual,
            "predicted_count": total_pred,
            "true_positive": int(true_pos),
            "precision": precision,
            "recall": recall,
        }

    return {
        "labels": labels,
        "matrix": cm_list,
        "per_class": per_class,
    }


def compute_operations_kpis(db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    """Fetch high-level operational throughput, backlog, and SLA metrics."""
    conn = sqlite3.connect(str(db_path))

    tasks_df = pd.read_sql_query("SELECT COUNT(*) AS total_tasks FROM tasks;", conn)
    valid_df = pd.read_sql_query(
        "SELECT COUNT(*) AS total_valid, COUNT(DISTINCT task_id) AS distinct_completed, AVG(processing_time_seconds) AS avg_time FROM annotations;",
        conn,
    )
    rej_df = pd.read_sql_query("SELECT COUNT(*) AS total_rejected FROM rejection_audit;", conn)

    total_tasks = int(tasks_df["total_tasks"].iloc[0]) if not tasks_df.empty else 0
    distinct_completed = int(valid_df["distinct_completed"].iloc[0] or 0) if not valid_df.empty else 0
    total_valid = int(valid_df["total_valid"].iloc[0] or 0) if not valid_df.empty else 0
    total_rejected = int(rej_df["total_rejected"].iloc[0] or 0) if not rej_df.empty else 0
    avg_proc_time = float(valid_df["avg_time"].iloc[0] or 0.0) if not valid_df.empty else 0.0

    # Calculate median time
    durations = pd.read_sql_query("SELECT processing_time_seconds FROM annotations;", conn)
    median_proc_time = float(durations["processing_time_seconds"].median()) if not durations.empty else 0.0

    total_submissions = total_valid + total_rejected
    rejection_rate_pct = round((total_rejected / total_submissions) * 100.0, 2) if total_submissions > 0 else 0.0
    completion_rate_pct = round((distinct_completed / total_tasks) * 100.0, 2) if total_tasks > 0 else 0.0
    pending_backlog = max(0, total_tasks - distinct_completed)

    conn.close()

    return {
        "total_tasks": total_tasks,
        "completed_tasks": distinct_completed,
        "total_valid_submissions": total_valid,
        "total_rejected_submissions": total_rejected,
        "total_submissions": total_submissions,
        "pending_backlog": pending_backlog,
        "completion_rate_pct": completion_rate_pct,
        "rejection_rate_pct": rejection_rate_pct,
        "avg_processing_time_seconds": round(avg_proc_time, 2),
        "median_processing_time_seconds": round(median_proc_time, 2),
    }


def compute_quality_kpis(db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    """Calculate accuracy, Cohen's Kappa, and error distribution against gold standard."""
    conn = sqlite3.connect(str(db_path))

    query = """
    SELECT 
        a.task_id,
        a.annotator_id,
        a.condition AS annotated_condition,
        g.ground_truth_condition,
        g.difficulty
    FROM annotations a
    JOIN gold_annotations g ON a.task_id = g.task_id;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        return {
            "total_gold_evaluated": 0,
            "accuracy_pct": 0.0,
            "error_rate_pct": 0.0,
            "cohens_kappa": 0.0,
            "confusion_matrix": calculate_confusion_matrix_data([], []),
            "difficulty_breakdown": {},
        }

    y_true = df["ground_truth_condition"].tolist()
    y_pred = df["annotated_condition"].tolist()

    matches = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    total = len(y_true)
    accuracy_pct = round((matches / total) * 100.0, 2)
    error_rate_pct = round(100.0 - accuracy_pct, 2)
    kappa = calculate_cohens_kappa(y_true, y_pred)
    cm_data = calculate_confusion_matrix_data(y_true, y_pred)

    # Breakdown by difficulty tier
    diff_stats = {}
    for diff in ["EASY", "MEDIUM", "HARD"]:
        sub = df[df["difficulty"] == diff]
        if not sub.empty:
            sub_matches = sum(1 for t, p in zip(sub["ground_truth_condition"], sub["annotated_condition"]) if t == p)
            diff_stats[diff] = {
                "total": len(sub),
                "correct": sub_matches,
                "accuracy_pct": round((sub_matches / len(sub)) * 100.0, 2),
            }

    return {
        "total_gold_evaluated": total,
        "accuracy_pct": accuracy_pct,
        "error_rate_pct": error_rate_pct,
        "cohens_kappa": kappa,
        "confusion_matrix": cm_data,
        "difficulty_breakdown": diff_stats,
    }


def compute_annotator_kpis(db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Compile per-annotator productivity, speed, rejection rate, and gold accuracy."""
    conn = sqlite3.connect(str(db_path))

    query = """
    WITH valid_stats AS (
        SELECT 
            annotator_id,
            COUNT(*) AS tasks_completed,
            AVG(processing_time_seconds) AS avg_duration_sec,
            SUM(CASE WHEN anomaly_flag IS NOT NULL THEN 1 ELSE 0 END) AS anomaly_count
        FROM annotations
        GROUP BY annotator_id
    ),
    rej_stats AS (
        SELECT 
            annotator_id,
            COUNT(*) AS rejections_count
        FROM rejection_audit
        WHERE annotator_id IS NOT NULL
        GROUP BY annotator_id
    ),
    gold_stats AS (
        SELECT 
            a.annotator_id,
            COUNT(*) AS gold_count,
            SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) AS gold_correct
        FROM annotations a
        JOIN gold_annotations g ON a.task_id = g.task_id
        GROUP BY a.annotator_id
    )
    SELECT 
        ann.annotator_id,
        ann.display_name,
        ann.role,
        COALESCE(v.tasks_completed, 0) AS tasks_completed,
        ROUND(COALESCE(v.avg_duration_sec, 0), 2) AS avg_duration_sec,
        COALESCE(v.anomaly_count, 0) AS anomaly_count,
        COALESCE(r.rejections_count, 0) AS rejections_count,
        ROUND(
            COALESCE(r.rejections_count, 0) * 100.0 / 
            NULLIF(COALESCE(v.tasks_completed, 0) + COALESCE(r.rejections_count, 0), 0),
            2
        ) AS rejection_rate_pct,
        COALESCE(g.gold_count, 0) AS gold_tasks_evaluated,
        ROUND(
            COALESCE(g.gold_correct, 0) * 100.0 / NULLIF(COALESCE(g.gold_count, 0), 0),
            2
        ) AS gold_accuracy_pct
    FROM annotators ann
    LEFT JOIN valid_stats v ON ann.annotator_id = v.annotator_id
    LEFT JOIN rej_stats r ON ann.annotator_id = r.annotator_id
    LEFT JOIN gold_stats g ON ann.annotator_id = g.annotator_id
    ORDER BY tasks_completed DESC;
    """

    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def compute_trend_kpis(db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, pd.DataFrame]:
    """Retrieve time-series trends for throughput, cycle time, quality, and rejections."""
    conn = sqlite3.connect(str(db_path))

    # Daily Volume and Speed
    daily_vol_query = """
    SELECT 
        SUBSTR(annotation_timestamp, 1, 10) AS date,
        COUNT(*) AS volume,
        ROUND(AVG(processing_time_seconds), 2) AS avg_time_sec
    FROM annotations
    GROUP BY SUBSTR(annotation_timestamp, 1, 10)
    ORDER BY date ASC;
    """
    daily_vol = pd.read_sql_query(daily_vol_query, conn)

    # Daily Quality vs Gold
    daily_qual_query = """
    SELECT 
        SUBSTR(a.annotation_timestamp, 1, 10) AS date,
        COUNT(*) AS gold_count,
        SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) AS correct_count,
        ROUND(
            SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
            2
        ) AS daily_accuracy_pct
    FROM annotations a
    JOIN gold_annotations g ON a.task_id = g.task_id
    GROUP BY SUBSTR(a.annotation_timestamp, 1, 10)
    ORDER BY date ASC;
    """
    daily_qual = pd.read_sql_query(daily_qual_query, conn)

    # Rejections by Code
    rej_query = """
    SELECT 
        rejection_code,
        validation_stage,
        COUNT(*) AS count
    FROM rejection_audit
    GROUP BY rejection_code, validation_stage
    ORDER BY count DESC;
    """
    rejections = pd.read_sql_query(rej_query, conn)

    conn.close()
    return {
        "daily_volume": daily_vol,
        "daily_quality": daily_qual,
        "rejection_summary": rejections,
    }
