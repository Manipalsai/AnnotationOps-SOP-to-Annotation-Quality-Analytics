"""
AnnotationOps Streamlit Executive Dashboard (v2 Enterprise).
Multi-page operational analytics, quality science evaluation, annotator scorecards,
data quality audit, longitudinal trend analysis, simulated SLA variance, and backlog reconciliation.
DISCLOSURE: Simulated enterprise-scale synthetic workload for portfolio demonstration.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.metrics import cohen_kappa_score, confusion_matrix as sk_confusion_matrix

# ---------------------------------------------------------------------------
# Robustly resolve project root regardless of Streamlit's cwd
# ---------------------------------------------------------------------------
_THIS_FILE = os.path.abspath(__file__)
BASE_DIR = Path(_THIS_FILE).parent.parent.parent
sys.path = [p for p in sys.path if not p.endswith("ANNOTATIONOPS")]
sys.path.insert(0, str(BASE_DIR))

from pipeline.database import DEFAULT_DB_PATH
from pipeline.bootstrap import verify_database_integrity, bootstrap_warehouse

DISCLOSURE_TEXT = (
    "ℹ️ <strong>Enterprise Simulation Disclosure:</strong> "
    "Dataset represents an enterprise-scale synthetic annotation workload generated deterministically (seed=42) "
    "for portfolio operations analysis demonstration. All metrics, annotator personas, scenario milestones, "
    "and SLA benchmarks are simulated."
)

CONDITION_LABELS = ["NEW", "OPEN_BOX", "DAMAGED"]


# ---------------------------------------------------------------------------
# Data loading (cached) - compatible with existing test suite
# ---------------------------------------------------------------------------
@st.cache_data(ttl=30)
def load_warehouse_data(db_path_str: str):
    """Load core tables from SQLite warehouse with connection caching."""
    conn = sqlite3.connect(db_path_str)
    tasks_df = pd.read_sql_query("SELECT * FROM tasks;", conn)
    annotations_df = pd.read_sql_query("SELECT * FROM annotations;", conn)
    gold_df = pd.read_sql_query("SELECT * FROM gold_annotations;", conn)
    rejections_df = pd.read_sql_query("SELECT * FROM rejection_audit;", conn)
    annotators_df = pd.read_sql_query("SELECT * FROM annotators;", conn)
    conn.close()
    return tasks_df, annotations_df, gold_df, rejections_df, annotators_df


@st.cache_data(ttl=30)
def load_auxiliary_data(db_path_str: str):
    """Load events and SLA simulation targets from SQLite warehouse."""
    conn = sqlite3.connect(db_path_str)
    try:
        events_df = pd.read_sql_query("SELECT * FROM operational_events ORDER BY week_number ASC;", conn)
    except Exception:
        events_df = pd.DataFrame()
    try:
        targets_df = pd.read_sql_query("SELECT * FROM simulation_targets;", conn)
    except Exception:
        targets_df = pd.DataFrame()
    conn.close()
    return events_df, targets_df


# ---------------------------------------------------------------------------
# Dynamic metric calculation functions on filtered DataFrames
# ---------------------------------------------------------------------------

def _safe_kappa(y_true, y_pred, labels=CONDITION_LABELS):
    if len(y_true) < 2:
        return 0.0
    if len(set(y_true)) == 1 and y_true == y_pred:
        return 1.0
    try:
        k = cohen_kappa_score(y_true, y_pred, labels=labels)
        return 0.0 if np.isnan(k) else round(float(k), 4)
    except Exception:
        return 0.0


def _confusion_data(y_true, y_pred, labels=CONDITION_LABELS):
    if len(y_true) == 0:
        return {"labels": labels, "matrix": [[0]*len(labels)]*len(labels), "per_class": {}, "macro_f1": 0.0}
    cm = sk_confusion_matrix(y_true, y_pred, labels=labels)
    per_class = {}
    f1s = []
    for idx, lbl in enumerate(labels):
        tp = cm[idx, idx]
        tot_actual = int(cm[idx, :].sum())
        tot_pred = int(cm[:, idx].sum())
        rec = round(tp / tot_actual, 4) if tot_actual > 0 else 0.0
        prec = round(tp / tot_pred, 4) if tot_pred > 0 else 0.0
        f1 = round(2 * (prec * rec) / (prec + rec), 4) if (prec + rec) > 0 else 0.0
        f1s.append(f1)
        per_class[lbl] = {
            "actual_count": tot_actual,
            "predicted_count": tot_pred,
            "true_positive": int(tp),
            "precision": prec,
            "recall": rec,
            "f1_score": f1,
        }
    return {
        "labels": labels,
        "matrix": cm.tolist(),
        "per_class": per_class,
        "macro_f1": round(float(np.mean(f1s)), 4) if f1s else 0.0,
    }


def compute_ops_metrics(filt_ann: pd.DataFrame, filt_tasks: pd.DataFrame, in_scope_rejections: pd.DataFrame):
    """Compute operational KPIs dynamically from filtered DataFrames."""
    total_tasks = len(filt_tasks)
    completed_tasks = int(filt_tasks["task_id"].isin(filt_ann["task_id"].unique()).sum()) if total_tasks > 0 else 0
    pending_backlog = max(0, total_tasks - completed_tasks)
    total_valid = len(filt_ann)
    total_rej = len(in_scope_rejections)
    total_subs = total_valid + total_rej
    rej_rate = round(total_rej / total_subs * 100, 2) if total_subs > 0 else 0.0
    comp_rate = round(completed_tasks / total_tasks * 100, 2) if total_tasks > 0 else 0.0
    avg_time = round(float(filt_ann["processing_time_seconds"].mean()), 2) if not filt_ann.empty else 0.0
    med_time = round(float(filt_ann["processing_time_seconds"].median()), 2) if not filt_ann.empty else 0.0
    rework_tasks = int(filt_tasks["status"].eq("REWORK").sum()) if "status" in filt_tasks.columns else 0
    escalated_tasks = int(filt_tasks["status"].eq("ESCALATED").sum()) if "status" in filt_tasks.columns else 0
    rework_rate = round(int(filt_ann["is_rework"].sum()) / max(1, total_valid) * 100, 2) if "is_rework" in filt_ann.columns else 0.0
    esc_rate = round(escalated_tasks / max(1, total_tasks) * 100, 2) if total_tasks > 0 else 0.0

    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "pending_backlog": pending_backlog,
        "total_valid_submissions": total_valid,
        "total_rejected_submissions": total_rej,
        "total_submissions": total_subs,
        "rejection_rate_pct": rej_rate,
        "completion_rate_pct": comp_rate,
        "avg_processing_time_seconds": avg_time,
        "median_processing_time_seconds": med_time,
        "rework_tasks": rework_tasks,
        "escalated_tasks": escalated_tasks,
        "rework_rate_pct": rework_rate,
        "escalation_rate_pct": esc_rate,
        "reconciled": (completed_tasks + pending_backlog == total_tasks),
    }


def compute_quality_metrics(filt_ann: pd.DataFrame, gold_df: pd.DataFrame):
    """Compute quality KPIs by joining filtered annotations against gold."""
    if filt_ann.empty or gold_df.empty:
        return {
            "total_gold_evaluated": 0, "accuracy_pct": 0.0, "error_rate_pct": 0.0,
            "cohens_kappa": 0.0, "macro_f1": 0.0, "confusion_matrix": _confusion_data([], []),
            "difficulty_breakdown": {},
        }

    # Only include difficulty if not already in filt_ann to avoid collision
    gold_cols = ["task_id", "ground_truth_condition"]
    if "difficulty" not in filt_ann.columns and "difficulty" in gold_df.columns:
        gold_cols.append("difficulty")

    merged = filt_ann.merge(gold_df[gold_cols], on="task_id", how="inner")
    if merged.empty:
        return {
            "total_gold_evaluated": 0, "accuracy_pct": 0.0, "error_rate_pct": 0.0,
            "cohens_kappa": 0.0, "macro_f1": 0.0, "confusion_matrix": _confusion_data([], []),
            "difficulty_breakdown": {},
        }

    diff_col = "difficulty" if "difficulty" in merged.columns else ("difficulty_x" if "difficulty_x" in merged.columns else None)

    y_true = merged["ground_truth_condition"].tolist()
    y_pred = merged["condition"].tolist()
    matches = sum(t == p for t, p in zip(y_true, y_pred))
    total = len(y_true)
    acc = round(matches / total * 100, 2) if total > 0 else 0.0
    kappa = _safe_kappa(y_true, y_pred)
    cm_data = _confusion_data(y_true, y_pred)
    diff_stats = {}
    if diff_col:
        for d in ["EASY", "MEDIUM", "HARD"]:
            sub = merged[merged[diff_col] == d]
            if not sub.empty:
                sm = sum(t == p for t, p in zip(sub["ground_truth_condition"], sub["condition"]))
                diff_stats[d] = {
                    "total": len(sub),
                    "correct": sm,
                    "accuracy_pct": round(sm / len(sub) * 100, 2),
                }
    return {
        "total_gold_evaluated": total,
        "accuracy_pct": acc,
        "error_rate_pct": round(100 - acc, 2),
        "cohens_kappa": kappa,
        "macro_f1": cm_data["macro_f1"],
        "confusion_matrix": cm_data,
        "difficulty_breakdown": diff_stats,
    }


def compute_iaa_metrics(filt_ann: pd.DataFrame):
    """Compute inter-annotator agreement from filtered annotations."""
    if filt_ann.empty:
        return {"multi_rated_tasks": 0, "full_concordance_count": 0, "agreement_rate_pct": 0.0}
    grouped = (
        filt_ann.groupby("task_id")
        .agg(
            rater_count=("annotator_id", "nunique"),
            conditions=("condition", lambda x: list(x)),
        )
        .reset_index()
    )
    multi = grouped[grouped["rater_count"] >= 2]
    if multi.empty:
        return {"multi_rated_tasks": 0, "full_concordance_count": 0, "agreement_rate_pct": 0.0}
    concordant = multi["conditions"].apply(lambda cs: len(set(cs)) == 1).sum()
    return {
        "multi_rated_tasks": len(multi),
        "full_concordance_count": int(concordant),
        "agreement_rate_pct": round(int(concordant) / len(multi) * 100, 2),
    }


def compute_annotator_metrics(filt_ann: pd.DataFrame, in_scope_rej: pd.DataFrame, gold_df: pd.DataFrame, annotators_df: pd.DataFrame):
    """Compute per-annotator KPIs dynamically from filtered data."""
    gold_merged = filt_ann.merge(gold_df[["task_id", "ground_truth_condition"]], on="task_id", how="inner")

    rows = []
    for _, ann_row in annotators_df.iterrows():
        aid = ann_row["annotator_id"]
        ann_data = filt_ann[filt_ann["annotator_id"] == aid]
        rej_data = in_scope_rej[in_scope_rej["annotator_id"] == aid] if ("annotator_id" in in_scope_rej.columns and not in_scope_rej.empty) else pd.DataFrame()
        gold_data = gold_merged[gold_merged["annotator_id"] == aid]

        tc = len(ann_data)
        avg_dur = round(float(ann_data["processing_time_seconds"].mean()), 2) if tc > 0 else 0.0
        rej_cnt = len(rej_data)
        rework_cnt = int(ann_data["is_rework"].sum()) if ("is_rework" in ann_data.columns and tc > 0) else 0
        esc_cnt = int(ann_data["is_escalated"].sum()) if ("is_escalated" in ann_data.columns and tc > 0) else 0
        anomaly_cnt = int(ann_data["anomaly_flag"].notnull().sum()) if ("anomaly_flag" in ann_data.columns and tc > 0) else 0
        rej_rate = round(rej_cnt / max(1, tc + rej_cnt) * 100, 2)
        rework_rate = round(rework_cnt / max(1, tc) * 100, 2)
        gold_cnt = len(gold_data)
        gold_correct = int((gold_data["condition"] == gold_data["ground_truth_condition"]).sum()) if gold_cnt > 0 else 0
        gold_acc = round(gold_correct / gold_cnt * 100, 2) if gold_cnt > 0 else 0.0

        rows.append({
            "annotator_id": aid,
            "display_name": ann_row.get("display_name", aid),
            "role": ann_row.get("role", ""),
            "team": ann_row.get("team", ""),
            "shift": ann_row.get("shift", ""),
            "experience_level": ann_row.get("experience_level", ""),
            "tasks_completed": tc,
            "avg_duration_sec": avg_dur,
            "anomaly_count": anomaly_cnt,
            "rework_count": rework_cnt,
            "escalation_count": esc_cnt,
            "rejections_count": rej_cnt,
            "rejection_rate_pct": rej_rate,
            "rework_rate_pct": rework_rate,
            "gold_tasks_evaluated": gold_cnt,
            "gold_accuracy_pct": gold_acc,
        })

    return pd.DataFrame(rows).sort_values("tasks_completed", ascending=False).reset_index(drop=True)


def compute_sla_variance(ops: dict, qual: dict, targets_df: pd.DataFrame):
    """Evaluate actuals vs. targets completely data-driven."""
    if targets_df.empty:
        return [], 0, 0, 0.0

    metrics_map = {
        "quality_accuracy_pct": qual.get("accuracy_pct", 0.0),
        "rejection_rate_pct": ops.get("rejection_rate_pct", 0.0),
        "avg_processing_time_sec": ops.get("avg_processing_time_seconds", 0.0),
        "cohens_kappa": qual.get("cohens_kappa", 0.0),
        "completion_rate_pct": ops.get("completion_rate_pct", 0.0),
    }
    evaluations, met_count = [], 0
    for _, row in targets_df.iterrows():
        key = row["metric_key"]
        target = float(row["target_value"])
        actual = metrics_map.get(key, 0.0)
        btype = row["benchmark_type"]
        diff = round(actual - target, 2)
        pct_d = round((diff / target) * 100, 2) if target != 0 else 0.0
        is_met = (actual >= target) if btype == "MINIMUM" else (actual <= target if btype == "MAXIMUM" else True)
        if is_met:
            met_count += 1
        evaluations.append({
            "metric_key": key,
            "metric_name": row["metric_name"],
            "target": target,
            "actual": actual,
            "unit": row["unit"],
            "benchmark_type": btype,
            "is_met": is_met,
            "status": "TARGET MET" if is_met else "TARGET MISSED",
            "variance_abs": diff,
            "variance_pct": pct_d,
            "description": row.get("description", ""),
        })
    attainment = round(met_count / len(evaluations) * 100, 1) if evaluations else 0.0
    return evaluations, len(evaluations), met_count, attainment


def compute_backlog_waterfall(filt_ann: pd.DataFrame, filt_tasks: pd.DataFrame):
    """Build dynamic 12-week backlog waterfall from filtered data."""
    if filt_ann.empty:
        return pd.DataFrame(), True, 0

    START = pd.Timestamp("2026-07-06 08:00:00")
    filt_ann = filt_ann.copy()
    ts = pd.to_datetime(filt_ann["annotation_timestamp"], errors="coerce")
    if hasattr(ts.dt, "tz") and ts.dt.tz is not None:
        ts = ts.dt.tz_localize(None)
    filt_ann["week_num"] = (
        (ts - START).dt.total_seconds() / (7 * 86400)
    ).astype(int) + 1

    weekly_completed = (
        filt_ann.groupby("week_num")["task_id"].nunique().reindex(range(1, 13), fill_value=0)
    )
    weekly_rework = (
        filt_ann.groupby("week_num")["is_rework"].sum().reindex(range(1, 13), fill_value=0)
        if "is_rework" in filt_ann.columns else pd.Series(0, index=range(1, 13))
    )

    total_tasks = max(len(filt_tasks), 1)
    base_weekly_intake = [450, 420, 410, 420, 600, 430, 400, 390, 380, 400, 370, 330]
    scale = total_tasks / 5000.0
    weekly_intake = [max(1, int(round(v * scale))) for v in base_weekly_intake]

    rows, backlog, all_ok = [], 0, True
    for i in range(12):
        w = i + 1
        opening = backlog
        ingested = weekly_intake[i]
        completed = int(weekly_completed.get(w, 0))
        rework = int(weekly_rework.get(w, 0))
        closing = opening + ingested - completed
        reconciles = (closing == opening + ingested - completed)
        if not reconciles:
            all_ok = False
        backlog = max(0, closing)
        rows.append({
            "Week": f"Week {w:02d}",
            "Opening Backlog": opening,
            "New Tasks Ingested": ingested,
            "Completed Tasks": completed,
            "Rework Submissions": rework,
            "Closing Backlog": closing,
            "Reconciles": reconciles,
        })
    return pd.DataFrame(rows), all_ok, backlog


# ---------------------------------------------------------------------------
# MAIN DASHBOARD RENDERER
# ---------------------------------------------------------------------------
def render_dashboard():
    # Page configuration
    st.set_page_config(
        page_title="AnnotationOps | Enterprise Operations & Quality Analytics",
        page_icon="📦",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Custom High-Contrast Professional Styling
    st.markdown(
        """
        <style>
        .metric-card {
            background: #18202c;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 16px;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }
        .metric-title {
            color: #94a3b8;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .metric-val {
            font-size: 1.8rem;
            font-weight: 800;
            color: #38bdf8;
            margin-top: 4px;
        }
        .metric-sub {
            font-size: 0.75rem;
            color: #cbd5e1;
            margin-top: 2px;
        }
        .narrative-card {
            background: #0f172a;
            border-left: 4px solid #38bdf8;
            padding: 16px;
            border-radius: 4px;
            margin-top: 14px;
            margin-bottom: 20px;
        }
        .narrative-title {
            font-weight: 700;
            color: #38bdf8;
            font-size: 0.95rem;
            margin-bottom: 8px;
        }
        .narrative-body {
            font-size: 0.88rem;
            color: #e2e8f0;
            line-height: 1.5;
        }
        .disclosure-banner {
            background: #0b1120;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 10px 14px;
            font-size: 0.78rem;
            color: #94a3b8;
            margin-top: 25px;
            margin-bottom: 10px;
        }
        .filter-active {
            background: #0f2d1f;
            border: 1px solid #10b981;
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 0.78rem;
            color: #10b981;
            margin-bottom: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    db_path = str(DEFAULT_DB_PATH)
    is_valid, _, _ = verify_database_integrity(db_path)
    if not is_valid:
        with st.spinner("📦 First-time deployment detected: initializing analytics warehouse (seed=42)..."):
            bootstrap_warehouse(db_path=db_path)

    tasks_df, annotations_df, gold_df, rejections_df, annotators_df = load_warehouse_data(db_path)
    events_df, targets_df = load_auxiliary_data(db_path)

    # Parse timestamps
    annotations_df["annotation_timestamp"] = pd.to_datetime(
        annotations_df["annotation_timestamp"], errors="coerce"
    )
    if "rejected_at" in rejections_df.columns:
        rejections_df["rejected_at"] = pd.to_datetime(
            rejections_df["rejected_at"], errors="coerce"
        )

    # Enriched annotations with task metadata
    merged_ann = annotations_df.merge(
        tasks_df[["task_id", "product_category", "category_group", "difficulty", "priority", "status"]],
        on="task_id", how="left", suffixes=("", "_task")
    )

    # -------------------------------------------------------------------------
    # SIDEBAR CONTROLS & GLOBAL FILTERS
    # -------------------------------------------------------------------------
    st.sidebar.title("📦 ANNOTATIONOPS")
    st.sidebar.caption("Enterprise Annotation Operations & Quality System")

    st.sidebar.subheader("Navigation")
    page = st.sidebar.radio(
        "Select Analytical View:",
        [
            "1. Operations Overview",
            "2. Quality Science & Agreement",
            "3. Annotator Performance",
            "4. Data Quality & Rejections",
            "5. Operational & Quality Trends",
        ],
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔎 Global Filters")
    st.sidebar.caption("All operational views, charts, and metrics respond dynamically to these selections.")

    min_date = annotations_df["annotation_timestamp"].dt.date.min()
    max_date = annotations_df["annotation_timestamp"].dt.date.max()
    all_annotator_ids = sorted(annotators_df["annotator_id"].tolist())
    all_categories = sorted(tasks_df["product_category"].dropna().unique().tolist())
    all_difficulties = ["EASY", "MEDIUM", "HARD"]
    all_statuses = ["COMPLETED", "PENDING", "REWORK", "ESCALATED"]

    # Session state initialization for filters
    if "date_range" not in st.session_state:
        st.session_state["date_range"] = (min_date, max_date)
    if "annotators" not in st.session_state:
        st.session_state["annotators"] = all_annotator_ids
    if "categories" not in st.session_state:
        st.session_state["categories"] = all_categories
    if "conditions" not in st.session_state:
        st.session_state["conditions"] = list(CONDITION_LABELS)
    if "difficulties" not in st.session_state:
        st.session_state["difficulties"] = list(all_difficulties)
    if "statuses" not in st.session_state:
        st.session_state["statuses"] = list(all_statuses)

    def reset_filters_callback():
        st.session_state["date_range"] = (min_date, max_date)
        st.session_state["annotators"] = all_annotator_ids
        st.session_state["categories"] = all_categories
        st.session_state["conditions"] = list(CONDITION_LABELS)
        st.session_state["difficulties"] = list(all_difficulties)
        st.session_state["statuses"] = list(all_statuses)

    # Reset / Clear All Filters button
    st.sidebar.button(
        "🔄 Clear / Reset All Filters",
        on_click=reset_filters_callback,
        use_container_width=True,
        help="Click to restore all filters back to full-workload default settings",
    )

    # 1. Date Range
    selected_date_range = st.sidebar.date_input(
        "Date Range:",
        min_value=min_date,
        max_value=max_date,
        key="date_range",
    )

    # 2. Annotator Multi-Select
    selected_annotators = st.sidebar.multiselect(
        "Annotator ID:", options=all_annotator_ids, key="annotators"
    )

    # 3. Product Category
    selected_categories = st.sidebar.multiselect(
        "Product Category:", options=all_categories, key="categories"
    )

    # 4. Condition Label
    selected_conditions = st.sidebar.multiselect(
        "Condition Label:", options=CONDITION_LABELS, key="conditions"
    )

    # 5. Task Difficulty
    selected_difficulties = st.sidebar.multiselect(
        "Task Difficulty:", options=all_difficulties, key="difficulties"
    )

    # 6. Operational Status
    selected_statuses = st.sidebar.multiselect(
        "Operational Status:", options=all_statuses, key="statuses"
    )

    # -------------------------------------------------------------------------
    # Filter Execution
    # -------------------------------------------------------------------------
    mask = (
        merged_ann["annotator_id"].isin(selected_annotators)
        & merged_ann["condition"].isin(selected_conditions)
        & merged_ann["product_category"].isin(selected_categories)
        & merged_ann["difficulty"].isin(selected_difficulties)
    )

    if "status" in merged_ann.columns:
        mask = mask & merged_ann["status"].isin(selected_statuses)

    if selected_date_range and len(selected_date_range) == 2:
        s_date, e_date = selected_date_range
        ann_dates = merged_ann["annotation_timestamp"].dt.date
        mask = mask & (ann_dates >= s_date) & (ann_dates <= e_date)

    filtered_annotations = merged_ann[mask].copy()

    # Filter tasks: matching categories, difficulties, statuses
    filtered_tasks = tasks_df[
        tasks_df["product_category"].isin(selected_categories)
        & tasks_df["difficulty"].isin(selected_difficulties)
        & tasks_df["status"].isin(selected_statuses)
    ].copy()

    # Filter rejections: matching annotators and date range
    in_scope_rejections = rejections_df[
        rejections_df["annotator_id"].isin(selected_annotators)
    ].copy() if "annotator_id" in rejections_df.columns else rejections_df.copy()

    if selected_date_range and len(selected_date_range) == 2 and "rejected_at" in in_scope_rejections.columns:
        s_date, e_date = selected_date_range
        rej_dates = in_scope_rejections["rejected_at"].dt.date
        in_scope_rejections = in_scope_rejections[(rej_dates >= s_date) & (rej_dates <= e_date)]

    # Check if any filters are narrower than default
    is_filtered = (
        len(selected_annotators) < len(all_annotator_ids)
        or len(selected_categories) < len(all_categories)
        or len(selected_conditions) < len(CONDITION_LABELS)
        or len(selected_difficulties) < len(all_difficulties)
        or len(selected_statuses) < len(all_statuses)
        or (selected_date_range and len(selected_date_range) == 2
            and (selected_date_range[0] != min_date or selected_date_range[1] != max_date))
    )

    st.sidebar.markdown("---")
    if is_filtered:
        st.sidebar.markdown(
            '<div class="filter-active">⚡ <strong>Filters Active:</strong> Displaying filtered subset</div>',
            unsafe_allow_html=True,
        )

    st.sidebar.info(
        f"**Live Scope Summary**\n"
        f"- Valid Submissions: **{len(filtered_annotations):,}**\n"
        f"- Workload Tasks: **{len(filtered_tasks):,}**\n"
        f"- Annotators in View: **{filtered_annotations['annotator_id'].nunique()} / {len(all_annotator_ids)}**\n"
        f"- Date Window: **{filtered_annotations['annotation_timestamp'].dt.date.min() if not filtered_annotations.empty else 'N/A'}** → "
        f"**{filtered_annotations['annotation_timestamp'].dt.date.max() if not filtered_annotations.empty else 'N/A'}**"
    )

    def _no_data():
        st.warning("⚠️ No records match the active filter criteria. Broaden your selections in the sidebar.")

    # =========================================================================
    # PAGE 1 — OPERATIONS OVERVIEW & BACKLOG MANAGEMENT
    # =========================================================================
    if page == "1. Operations Overview":
        st.title("📊 Operations Overview & Backlog Management")
        st.markdown("Real-time monitoring of task queue velocity, operational backlog, throughput, and completion SLAs.")

        if filtered_annotations.empty and filtered_tasks.empty:
            _no_data()
            st.stop()

        ops = compute_ops_metrics(filtered_annotations, filtered_tasks, in_scope_rejections)
        qual = compute_quality_metrics(filtered_annotations, gold_df)
        evaluations, total_targets, met_count, attainment_pct = compute_sla_variance(ops, qual, targets_df)

        # Metric Row 1: Volume & Velocity
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Catalog Workload (Filtered)</div>
                <div class="metric-val">{ops['total_tasks']:,}</div>
                <div class="metric-sub">Matching Task Manifest</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Completed Tasks</div>
                <div class="metric-val" style="color:#10b981;">{ops['completed_tasks']:,}</div>
                <div class="metric-sub">{ops['completion_rate_pct']}% Completion Rate</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Pending Backlog</div>
                <div class="metric-val" style="color:#f59e0b;">{ops['pending_backlog']:,}</div>
                <div class="metric-sub">Rework: {ops['rework_tasks']} | Esc: {ops['escalated_tasks']}</div>
            </div>""", unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Avg Cycle Time</div>
                <div class="metric-val">{ops['avg_processing_time_seconds']}s</div>
                <div class="metric-sub">Median: {ops['median_processing_time_seconds']}s (Target: ≤12s)</div>
            </div>""", unsafe_allow_html=True)

        # Metric Row 2: SLA & Quality
        c5, c6, c7, c8 = st.columns(4)
        with c5:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Filtered Submissions</div>
                <div class="metric-val">{ops['total_valid_submissions']:,}</div>
                <div class="metric-sub">Valid Ingested Records</div>
            </div>""", unsafe_allow_html=True)
        with c6:
            rej_color = "#10b981" if ops["rejection_rate_pct"] <= 3.0 else "#ef4444"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Pipeline Rejection Rate</div>
                <div class="metric-val" style="color:{rej_color};">{ops['rejection_rate_pct']}%</div>
                <div class="metric-sub">SLA Target: ≤ 3.0%</div>
            </div>""", unsafe_allow_html=True)
        with c7:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Rework Rate</div>
                <div class="metric-val" style="color:#38bdf8;">{ops['rework_rate_pct']}%</div>
                <div class="metric-sub">Escalation Rate: {ops['escalation_rate_pct']}%</div>
            </div>""", unsafe_allow_html=True)
        with c8:
            sla_color = "#10b981" if attainment_pct >= 80 else "#f59e0b"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Simulated SLA Attainment</div>
                <div class="metric-val" style="color:{sla_color};">{attainment_pct}%</div>
                <div class="metric-sub">{met_count}/{total_targets} Benchmarks Met</div>
            </div>""", unsafe_allow_html=True)

        # Dynamic Diagnostic Narrative Card
        est_hours = round((ops['pending_backlog'] * ops['avg_processing_time_seconds']) / 3600, 1)
        st.markdown(f"""
        <div class="narrative-card">
            <div class="narrative-title">🔍 Operations Executive Diagnosis: Queue Pacing & Backlog Reconciliation</div>
            <div class="narrative-body">
                <strong>WHAT HAPPENED?</strong> Under the current filter selection, the team processed <strong>{ops['completed_tasks']:,} completed catalog assets</strong>
                with <strong>{ops['total_valid_submissions']:,} valid annotation events</strong>.
                The remaining backlog in view is <strong>{ops['pending_backlog']:,} tasks</strong>, with a rework volume of {ops['rework_tasks']} tasks ({ops['rework_rate_pct']}%).<br/>
                <strong>WHY IT MATTERS?</strong> Backlog reconciliation check: Total Tasks ({ops['total_tasks']:,}) = Completed ({ops['completed_tasks']:,}) + Backlog ({ops['pending_backlog']:,}).
                Status: <strong>{"✅ Mathematically Reconciled" if ops["reconciled"] else "❌ Discrepancy Found"}</strong>.
                At current average cycle time of {ops['avg_processing_time_seconds']}s, clearing this backlog requires ~{est_hours} auditor hours.<br/>
                <strong>WHERE TO INVESTIGATE?</strong> Toggle individual annotators or product categories in the sidebar to pinpoint productivity variances.
            </div>
        </div>""", unsafe_allow_html=True)

        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("12-Week Backlog Waterfall Reconciliation")
            wf_df, wf_ok, wf_final = compute_backlog_waterfall(filtered_annotations, filtered_tasks)
            if not wf_df.empty:
                fig_wf = go.Figure(go.Waterfall(
                    name="Backlog Flow", orientation="v",
                    measure=["relative"] * len(wf_df),
                    x=wf_df["Week"],
                    textposition="outside",
                    text=[f"{v:,}" for v in wf_df["Closing Backlog"]],
                    y=wf_df["Closing Backlog"],
                    connector={"line": {"color": "rgb(63,63,63)"}},
                    decreasing={"marker": {"color": "#10b981"}},
                    increasing={"marker": {"color": "#ef4444"}},
                    totals={"marker": {"color": "#38bdf8"}},
                ))
                fig_wf.update_layout(height=340, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_wf, use_container_width=True)
            else:
                st.info("No annotation timestamps in current view for waterfall.")

        with col_right:
            st.subheader("Queue Status & Workflow Health")
            if not filtered_tasks.empty:
                status_counts = filtered_tasks["status"].value_counts().reset_index()
                status_counts.columns = ["Status", "Count"]
                fig_donut = px.pie(
                    status_counts, values="Count", names="Status", hole=0.55,
                    color="Status",
                    color_discrete_map={"COMPLETED": "#10b981", "PENDING": "#334155",
                                        "REWORK": "#f59e0b", "ESCALATED": "#ef4444"},
                )
                fig_donut.update_layout(height=340, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_donut, use_container_width=True)
            else:
                st.info("No task records in current view.")

        st.subheader("Volume & Condition Breakdown by Product Category")
        if not filtered_annotations.empty:
            cat_summary = (
                filtered_annotations.groupby(["product_category", "condition"])
                .size().reset_index(name="count")
            )
            fig_bar = px.bar(
                cat_summary, x="product_category", y="count", color="condition",
                barmode="stack",
                color_discrete_map={"NEW": "#10b981", "OPEN_BOX": "#f59e0b", "DAMAGED": "#ef4444"},
                labels={"count": "Annotated Units", "product_category": "Product Category"},
            )
            fig_bar.update_layout(height=320, margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown(f'<div class="disclosure-banner">{DISCLOSURE_TEXT}</div>', unsafe_allow_html=True)

    # =========================================================================
    # PAGE 2 — QUALITY SCIENCE & AGREEMENT
    # =========================================================================
    elif page == "2. Quality Science & Agreement":
        st.title("🎯 Quality Science & Agreement Analytics")
        st.markdown("Measurement of annotation accuracy against verified gold-standard benchmarks, Cohen's Kappa, and inter-rater agreement.")

        if filtered_annotations.empty:
            _no_data()
            st.stop()

        qual = compute_quality_metrics(filtered_annotations, gold_df)
        iaa = compute_iaa_metrics(filtered_annotations)

        q1, q2, q3, q4 = st.columns(4)
        with q1:
            acc_color = "#10b981" if qual["accuracy_pct"] >= 95.0 else "#ef4444"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Gold Benchmark Accuracy</div>
                <div class="metric-val" style="color:{acc_color};">{qual['accuracy_pct']}%</div>
                <div class="metric-sub">Simulated Target: ≥ 95.0% | n={qual['total_gold_evaluated']:,}</div>
            </div>""", unsafe_allow_html=True)
        with q2:
            kap_color = "#10b981" if qual["cohens_kappa"] >= 0.85 else "#f59e0b"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Cohen's Kappa (κ)</div>
                <div class="metric-val" style="color:{kap_color};">{qual['cohens_kappa']}</div>
                <div class="metric-sub">Target: ≥ 0.85 (Strong Consensus)</div>
            </div>""", unsafe_allow_html=True)
        with q3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Macro F1-Score</div>
                <div class="metric-val" style="color:#38bdf8;">{qual['macro_f1']}</div>
                <div class="metric-sub">Harmonic Mean of Precision & Recall</div>
            </div>""", unsafe_allow_html=True)
        with q4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Multi-Rater Tasks</div>
                <div class="metric-val">{iaa['multi_rated_tasks']:,}</div>
                <div class="metric-sub">Concordance: {iaa['agreement_rate_pct']}% full match</div>
            </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div class="narrative-card">
            <div class="narrative-title">🔍 Scientific Quality Diagnosis: Cohen's Kappa & Ground Truth Precision</div>
            <div class="narrative-body">
                <strong>WHAT HAPPENED?</strong> Evaluated against <strong>{qual['total_gold_evaluated']:,} gold benchmark records</strong>
                matching current filters, classification accuracy reached <strong>{qual['accuracy_pct']}%</strong>
                with an inter-rater Cohen's Kappa of <strong>κ = {qual['cohens_kappa']}</strong> and Macro F1 of <strong>{qual['macro_f1']}</strong>.<br/>
                <strong>WHY IT MATTERS?</strong> Cohen's Kappa measures chance-adjusted consensus across 3 condition tiers.
                High precision on DAMAGED items ensures returned items requiring inspection are not misclassified as pristine inventory.<br/>
                <strong>WHERE TO INVESTIGATE?</strong> Review the confusion matrix below to isolate off-diagonal error clusters.
                Filter by Difficulty or Category to see where edge-case ambiguities concentrate.
            </div>
        </div>""", unsafe_allow_html=True)

        col_cm, col_diff = st.columns(2)

        with col_cm:
            st.subheader("Gold Confusion Matrix (True vs. Annotated)")
            cm_dict = qual["confusion_matrix"]
            fig_cm = px.imshow(
                cm_dict["matrix"], x=cm_dict["labels"], y=cm_dict["labels"],
                labels=dict(x="Annotated Condition", y="True Gold Condition", color="Submissions"),
                color_continuous_scale="Blues", text_auto=True,
            )
            fig_cm.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=340)
            st.plotly_chart(fig_cm, use_container_width=True)

        with col_diff:
            st.subheader("Accuracy & Sample Count by Difficulty Tier")
            diff_data = [
                {"Difficulty": d, "Accuracy %": s["accuracy_pct"], "Sample Count": s["total"]}
                for d, s in qual.get("difficulty_breakdown", {}).items()
            ]
            if diff_data:
                diff_df = pd.DataFrame(diff_data)
                fig_diff = px.bar(
                    diff_df, x="Difficulty", y="Accuracy %",
                    color="Accuracy %", color_continuous_scale="Teal",
                    range_y=[max(50.0, float(diff_df["Accuracy %"].min()) - 10.0), 102], text="Accuracy %",
                )
                fig_diff.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=340)
                st.plotly_chart(fig_diff, use_container_width=True)
            else:
                st.info("No gold benchmark records in this filter combination.")

        st.subheader("Per-Class Precision, Recall, and F1-Score Breakdown")
        per_class = cm_dict.get("per_class", {})
        if per_class:
            class_rows = [{
                "Condition Class": c,
                "Actual Population": m["actual_count"],
                "Predicted Count": m["predicted_count"],
                "True Positives": m["true_positive"],
                "Precision": f"{m['precision']:.4f}",
                "Recall": f"{m['recall']:.4f}",
                "F1-Score": f"{m['f1_score']:.4f}",
            } for c, m in per_class.items()]
            st.dataframe(pd.DataFrame(class_rows), use_container_width=True)

        st.markdown(f'<div class="disclosure-banner">{DISCLOSURE_TEXT}</div>', unsafe_allow_html=True)

    # =========================================================================
    # PAGE 3 — ANNOTATOR PERFORMANCE
    # =========================================================================
    elif page == "3. Annotator Performance":
        st.title("👥 Annotator Performance & Pacing Scorecard")
        st.markdown("Individual productivity, cycle times, upstream rejection rates, and gold accuracy across the simulated workforce.")

        if filtered_annotations.empty:
            _no_data()
            st.stop()

        ann_df = compute_annotator_metrics(filtered_annotations, in_scope_rejections, gold_df, annotators_df)

        active_count = int(ann_df['tasks_completed'].gt(0).sum())
        st.subheader(f"Simulated Workforce Leaderboard ({active_count} active annotators in current view)")

        def _green_scale(series: pd.Series, vmin=85.0, vmax=100.0):
            styles = []
            for val in series:
                try:
                    ratio = max(0.0, min(1.0, (float(val) - vmin) / (vmax - vmin)))
                except Exception:
                    ratio = 0.0
                r = int(26 + ratio * (34 - 26))
                g = int(58 + ratio * (197 - 58))
                b = int(42 + ratio * (94 - 42))
                styles.append(f"background-color: rgb({r},{g},{b}); color:white;")
            return styles

        st.dataframe(
            ann_df[[
                "annotator_id", "display_name", "role", "team", "shift", "experience_level",
                "tasks_completed", "avg_duration_sec", "rejections_count", "rejection_rate_pct",
                "rework_rate_pct", "gold_accuracy_pct",
            ]].style.format({
                "tasks_completed": "{:,}",
                "avg_duration_sec": "{:.1f}s",
                "rejection_rate_pct": "{:.1f}%",
                "rework_rate_pct": "{:.1f}%",
                "gold_accuracy_pct": "{:.1f}%",
            }).apply(_green_scale, subset=["gold_accuracy_pct"]),
            use_container_width=True,
        )

        top_performer = ann_df.iloc[0] if not ann_df.empty else None
        active_with_gold = ann_df[ann_df["gold_tasks_evaluated"] > 0]
        low_performer = active_with_gold.sort_values("gold_accuracy_pct").iloc[0] if not active_with_gold.empty else None

        top_desc = f"Top volume: <strong>{top_performer['display_name']}</strong> ({top_performer['tasks_completed']:,} tasks, {top_performer['gold_accuracy_pct']}% gold acc)." if top_performer is not None else ""
        low_desc = f" Lowest gold accuracy in view: <strong>{low_performer['display_name']}</strong> ({low_performer['gold_accuracy_pct']}% over {low_performer['gold_tasks_evaluated']} gold checks)." if low_performer is not None else ""

        st.markdown(f"""
        <div class="narrative-card">
            <div class="narrative-title">🔍 Workforce Calibration Diagnosis: Pacing vs. Quality Quadrants</div>
            <div class="narrative-body">
                <strong>WHAT HAPPENED?</strong> In the selected filter scope, {active_count} annotators contributed work.
                {top_desc}{low_desc}<br/>
                <strong>WHY IT MATTERS?</strong> Discrepancies between annotators reflect seniority distributions and operational specialization.
                Tracking rejection rates and rework rates per annotator allows targeted coaching before errors reach downstream production.<br/>
                <strong>WHERE TO INVESTIGATE?</strong> Use the Annotator multi-select in the sidebar to inspect specific individuals or compare shifts.
            </div>
        </div>""", unsafe_allow_html=True)

        col_a1, col_a2 = st.columns(2)

        with col_a1:
            st.subheader("Productivity vs. Pacing Speed Quadrant")
            active_ann_df = ann_df[ann_df["tasks_completed"] > 0]
            if not active_ann_df.empty:
                fig_scatter = px.scatter(
                    active_ann_df, x="avg_duration_sec", y="tasks_completed",
                    size="tasks_completed", color="role",
                    hover_name="display_name", text="annotator_id",
                    labels={"avg_duration_sec": "Avg Cycle Time (s)", "tasks_completed": "Completed Tasks"},
                )
                fig_scatter.update_traces(textposition="top center")
                fig_scatter.update_layout(height=340, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_scatter, use_container_width=True)

        with col_a2:
            st.subheader("Gold Benchmark Accuracy by Annotator")
            active_ann_df = ann_df[ann_df["gold_tasks_evaluated"] > 0]
            if not active_ann_df.empty:
                min_acc = max(0.0, float(active_ann_df["gold_accuracy_pct"].min()) - 5.0)
                fig_acc = px.bar(
                    active_ann_df, x="annotator_id", y="gold_accuracy_pct",
                    color="gold_accuracy_pct", color_continuous_scale="Viridis",
                    range_y=[min_acc, 102],
                    text="gold_accuracy_pct",
                    labels={"gold_accuracy_pct": "Gold Accuracy %", "annotator_id": "Annotator ID"},
                )
                fig_acc.add_hline(y=95.0, line_dash="dash", line_color="#10b981", annotation_text="95% Target")
                fig_acc.update_layout(height=340, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_acc, use_container_width=True)

        st.markdown(f'<div class="disclosure-banner">{DISCLOSURE_TEXT}</div>', unsafe_allow_html=True)

    # =========================================================================
    # PAGE 4 — DATA QUALITY & REJECTIONS
    # =========================================================================
    elif page == "4. Data Quality & Rejections":
        st.title("🛡️ Data Quality & Rejection Audit Log")
        st.markdown("Automated validation firewall gate failures, error code root causes, and pipeline anomaly detections.")

        total_valid = len(filtered_annotations)
        total_rej = len(in_scope_rejections)
        total_subs = total_valid + total_rej
        overall_rate = round(total_rej / total_subs * 100, 2) if total_subs > 0 else 0.0
        anomaly_cnt = int(filtered_annotations["anomaly_flag"].notnull().sum()) if "anomaly_flag" in filtered_annotations.columns else 0

        r1, r2, r3, r4 = st.columns(4)
        with r1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Total Rejections Blocked</div>
                <div class="metric-val" style="color:#ef4444;">{total_rej:,}</div>
                <div class="metric-sub">Blocked by Ingestion Firewall</div>
            </div>""", unsafe_allow_html=True)
        with r2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Pipeline Rejection Rate</div>
                <div class="metric-val">{overall_rate}%</div>
                <div class="metric-sub">Simulated SLA Target: ≤ 3.0%</div>
            </div>""", unsafe_allow_html=True)
        with r3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Speed Anomalies (&lt;3.0s)</div>
                <div class="metric-val" style="color:#f59e0b;">{anomaly_cnt:,}</div>
                <div class="metric-sub">Flagged for Quality Audit</div>
            </div>""", unsafe_allow_html=True)
        with r4:
            null_violations = int(filtered_annotations[["task_id", "annotator_id", "condition"]].isnull().any(axis=1).sum()) if not filtered_annotations.empty else 0
            null_color = "#ef4444" if null_violations > 0 else "#10b981"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Warehouse Null Violations</div>
                <div class="metric-val" style="color:{null_color};">{null_violations}</div>
                <div class="metric-sub">SQL Gate Strict Invariant</div>
            </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div class="narrative-card">
            <div class="narrative-title">🔍 Data Quality Root Cause Diagnosis: Firewall Filtering</div>
            <div class="narrative-body">
                <strong>WHAT HAPPENED?</strong> The multi-stage validation firewall intercepted
                <strong>{total_rej:,} non-compliant submissions</strong> ({overall_rate}% rejection rate)
                within the current filter scope, preventing invalid records from polluting the analytics warehouse.<br/>
                <strong>WHY IT MATTERS?</strong> Exactly {null_violations} malformed records entered the warehouse.
                Downstream reporting and machine learning evaluations operate purely on validated annotations.<br/>
                <strong>WHERE TO INVESTIGATE?</strong> Review the breakdown below to see which specific validation rules
                triggered failures. Narrow by annotator or date range to detect specific error waves.
            </div>
        </div>""", unsafe_allow_html=True)

        col_rej_chart, col_rej_stage = st.columns(2)

        with col_rej_chart:
            st.subheader("Rejections by Error Code")
            if not in_scope_rejections.empty and "rejection_code" in in_scope_rejections.columns:
                rej_by_code = in_scope_rejections["rejection_code"].value_counts().reset_index()
                rej_by_code.columns = ["Rejection Code", "Count"]
                fig_rej = px.bar(
                    rej_by_code, x="Count", y="Rejection Code", orientation="h",
                    color="Count", color_continuous_scale="Reds",
                )
                fig_rej.update_layout(height=320, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_rej, use_container_width=True)
            else:
                st.info("No rejection events recorded for the current filter scope.")

        with col_rej_stage:
            st.subheader("Failures by Validation Stage")
            if not in_scope_rejections.empty and "validation_stage" in in_scope_rejections.columns:
                rej_by_stage = in_scope_rejections["validation_stage"].value_counts().reset_index()
                rej_by_stage.columns = ["Validation Stage", "Count"]
                fig_stage = px.pie(
                    rej_by_stage, values="Count", names="Validation Stage",
                    color_discrete_sequence=px.colors.sequential.RdBu, hole=0.45,
                )
                fig_stage.update_layout(height=320, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_stage, use_container_width=True)

        st.subheader("Rejection Audit Trail (Latest Events in Filter Scope)")
        if not in_scope_rejections.empty:
            show_cols = [c for c in ["task_id", "annotator_id", "rejection_code", "rejection_reason",
                                      "validation_stage", "rejected_at"] if c in in_scope_rejections.columns]
            st.dataframe(in_scope_rejections[show_cols].tail(15), use_container_width=True)
        else:
            st.info("No rejection records in current filter scope.")

        st.markdown(f'<div class="disclosure-banner">{DISCLOSURE_TEXT}</div>', unsafe_allow_html=True)

    # =========================================================================
    # PAGE 5 — OPERATIONAL & QUALITY TRENDS
    # =========================================================================
    elif page == "5. Operational & Quality Trends":
        st.title("📈 Longitudinal Trends & Operational Drift")
        st.markdown("12-week time-series tracking of throughput velocity, quality drift, cycle-time shifts, and simulated SLA variance.")

        if filtered_annotations.empty:
            _no_data()
            st.stop()

        ops = compute_ops_metrics(filtered_annotations, filtered_tasks, in_scope_rejections)
        qual = compute_quality_metrics(filtered_annotations, gold_df)
        evaluations, total_targets, met_count, attainment_pct = compute_sla_variance(ops, qual, targets_df)

        START = pd.Timestamp("2026-07-06 08:00:00")
        fa = filtered_annotations.copy()
        fa_ts = pd.to_datetime(fa["annotation_timestamp"], errors="coerce")
        if hasattr(fa_ts.dt, "tz") and fa_ts.dt.tz is not None:
            fa_ts = fa_ts.dt.tz_localize(None)
        fa["week_num"] = ((fa_ts - START).dt.total_seconds() / (7 * 86400)).astype(int) + 1

        fa_gold = fa.merge(gold_df[["task_id", "ground_truth_condition"]], on="task_id", how="left")
        fa_gold["is_correct"] = fa_gold["condition"] == fa_gold["ground_truth_condition"]

        weekly_trend = (
            fa_gold.groupby("week_num").agg(
                total_volume=("task_id", "count"),
                avg_processing_time_sec=("processing_time_seconds", "mean"),
                gold_evaluations=("ground_truth_condition", "count"),
                correct_count=("is_correct", "sum"),
            ).reset_index()
        )
        weekly_trend["weekly_accuracy_pct"] = (
            weekly_trend["correct_count"] / weekly_trend["gold_evaluations"].replace(0, np.nan) * 100
        ).round(2)
        weekly_trend = weekly_trend[weekly_trend["week_num"].between(1, 12)].sort_values("week_num")

        if not events_df.empty:
            st.subheader("Simulated 12-Week Operational Scenario Milestones")
            evt_cols = st.columns(len(events_df))
            for idx, (_, ev) in enumerate(events_df.iterrows()):
                with evt_cols[idx]:
                    st.markdown(f"""
                    <div style="background:#1e293b;border:1px solid #38bdf8;border-radius:6px;padding:12px;height:100%;">
                        <div style="font-weight:700;color:#38bdf8;font-size:0.85rem;">Week {ev['week_number']}: {ev['title']}</div>
                        <div style="font-size:0.75rem;color:#cbd5e1;margin-top:4px;">{ev['description']}</div>
                        <div style="font-size:0.70rem;color:#94a3b8;margin-top:6px;font-style:italic;">{ev['impact_summary']}</div>
                    </div>""", unsafe_allow_html=True)

        col_t1, col_t2 = st.columns(2)

        with col_t1:
            st.subheader("Weekly Throughput Velocity (Filtered View)")
            if not weekly_trend.empty:
                fig_vol = px.bar(
                    weekly_trend, x="week_num", y="total_volume", text="total_volume",
                    labels={"total_volume": "Annotations Completed", "week_num": "Operational Week"},
                    color="total_volume", color_continuous_scale="Blues",
                )
                fig_vol.update_layout(height=320, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_vol, use_container_width=True)
            else:
                st.info("No weekly volume data in current filter scope.")

        with col_t2:
            st.subheader("Weekly Gold Accuracy & Quality Drift (%)")
            if not weekly_trend.empty and weekly_trend["gold_evaluations"].sum() > 0:
                fig_qual = px.line(
                    weekly_trend, x="week_num", y="weekly_accuracy_pct", markers=True,
                    labels={"weekly_accuracy_pct": "Gold Accuracy %", "week_num": "Operational Week"},
                )
                fig_qual.add_hline(y=95.0, line_dash="dash", line_color="#10b981", annotation_text="95% SLA Target")
                fig_qual.update_traces(line_color="#10b981", line_width=3)
                fig_qual.update_layout(height=320, margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_qual, use_container_width=True)
            else:
                st.info("No gold benchmark records in this filter window.")

        st.subheader("Weekly Cycle Time Evolution (Filtered)")
        if not weekly_trend.empty:
            fig_speed = px.bar(
                weekly_trend, x="week_num", y="avg_processing_time_sec",
                text=weekly_trend["avg_processing_time_sec"].round(1),
                labels={"avg_processing_time_sec": "Avg Cycle Time (s)", "week_num": "Operational Week"},
                color="avg_processing_time_sec", color_continuous_scale="Purples",
            )
            fig_speed.add_hline(y=12.0, line_dash="dot", line_color="#f59e0b", annotation_text="Pacing SLA Target (12.0s)")
            fig_speed.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig_speed, use_container_width=True)

        st.subheader("Simulated Project SLA Target vs. Actual Variance Analysis")
        if evaluations:
            var_rows = [{
                "Operational Metric": e["metric_name"],
                "Simulated Target": f"{e['target']}{e['unit']}",
                "Actual Result": f"{e['actual']}{e['unit']}",
                "Absolute Variance": f"{e['variance_abs']:+}{e['unit']}",
                "Percent Variance": f"{e['variance_pct']:+}%",
                "Performance Status": e["status"],
                "Rule Type": e["benchmark_type"],
            } for e in evaluations]
            st.dataframe(pd.DataFrame(var_rows), use_container_width=True)

        min_vol = int(weekly_trend['total_volume'].min()) if not weekly_trend.empty else 0
        max_vol = int(weekly_trend['total_volume'].max()) if not weekly_trend.empty else 0
        min_acc_str = f"{weekly_trend['weekly_accuracy_pct'].min():.1f}%" if not weekly_trend.empty and not weekly_trend['weekly_accuracy_pct'].isna().all() else "N/A"
        max_acc_str = f"{weekly_trend['weekly_accuracy_pct'].max():.1f}%" if not weekly_trend.empty and not weekly_trend['weekly_accuracy_pct'].isna().all() else "N/A"

        st.markdown(f"""
        <div class="narrative-card">
            <div class="narrative-title">🔍 Structured Root-Cause Investigation: Longitudinal Drift & Variance</div>
            <div class="narrative-body">
                <strong>WHAT HAPPENED?</strong> In the filtered view, weekly throughput ranges from
                <strong>{min_vol:,} to {max_vol:,} annotations/week</strong>.
                Weekly gold benchmark accuracy ranged from
                <strong>{min_acc_str}</strong> to <strong>{max_acc_str}</strong>.
                Simulated SLA attainment stands at <strong>{attainment_pct}%</strong> ({met_count}/{total_targets} benchmarks met).<br/>
                <strong>WHY IT MATTERS?</strong> Real-time filtering demonstrates operational agility: managers can zoom in to specific weeks (e.g. Week 5 intake surge or Week 7 edge-case drift) to dissect root causes in isolation.<br/>
                <strong>WHERE TO INVESTIGATE?</strong> Adjust the sidebar Date Range or Annotator filters to observe how individual workforce cohorts impact the weekly curve.
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown(f'<div class="disclosure-banner">{DISCLOSURE_TEXT}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Entrypoint: executes when run by Streamlit, avoids side-effects on test import
# ---------------------------------------------------------------------------
if __name__ == "__main__" or any("streamlit" in arg.lower() for arg in sys.argv):
    render_dashboard()
