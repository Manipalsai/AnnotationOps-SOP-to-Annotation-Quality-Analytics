"""
Unit tests for Dynamic Global Filtering.
Uses self-contained test DB fixture — no pre-generated files required.
"""

import pandas as pd
from app.dashboard.app import (
    load_warehouse_data,
    compute_ops_metrics,
    compute_quality_metrics,
    compute_annotator_metrics,
    compute_backlog_waterfall,
)


def test_dynamic_operational_filtering(test_db_path):
    tasks_df, annotations_df, gold_df, rejections_df, annotators_df = load_warehouse_data(str(test_db_path))
    ops_full = compute_ops_metrics(annotations_df, tasks_df, rejections_df)

    damaged_ann = annotations_df[annotations_df["condition"] == "DAMAGED"]
    ops_damaged = compute_ops_metrics(damaged_ann, tasks_df, rejections_df)

    assert ops_damaged["total_valid_submissions"] <= ops_full["total_valid_submissions"]
    assert ops_damaged["total_valid_submissions"] == len(damaged_ann)
    assert ops_damaged["reconciled"] is True


def test_dynamic_quality_filtering_by_difficulty(test_db_path):
    tasks_df, annotations_df, gold_df, rejections_df, annotators_df = load_warehouse_data(str(test_db_path))
    ann_merged = annotations_df.merge(tasks_df[["task_id", "difficulty"]], on="task_id", how="left")

    easy_ann = ann_merged[ann_merged["difficulty"] == "EASY"]
    hard_ann = ann_merged[ann_merged["difficulty"] == "HARD"]

    qual_easy = compute_quality_metrics(easy_ann, gold_df)
    qual_hard = compute_quality_metrics(hard_ann, gold_df)

    # Both return valid structures regardless of whether gold records exist
    assert "accuracy_pct" in qual_easy
    assert "accuracy_pct" in qual_hard
    assert 0.0 <= qual_easy["accuracy_pct"] <= 100.0
    assert 0.0 <= qual_hard["accuracy_pct"] <= 100.0


def test_dynamic_annotator_scorecard_filtering(test_db_path):
    tasks_df, annotations_df, gold_df, rejections_df, annotators_df = load_warehouse_data(str(test_db_path))

    ann_df_full = compute_annotator_metrics(annotations_df, rejections_df, gold_df, annotators_df)
    total_full = ann_df_full["tasks_completed"].sum()

    new_ann = annotations_df[annotations_df["condition"] == "NEW"]
    ann_df_new = compute_annotator_metrics(new_ann, rejections_df, gold_df, annotators_df)
    total_new = ann_df_new["tasks_completed"].sum()

    assert total_new <= total_full
    assert total_new == len(new_ann)


def test_dynamic_backlog_waterfall_filtering(test_db_path):
    tasks_df, annotations_df, _, _, _ = load_warehouse_data(str(test_db_path))

    wf_full, ok_full, _ = compute_backlog_waterfall(annotations_df, tasks_df)
    assert ok_full is True

    if len(tasks_df) > 10:
        subset_tasks = tasks_df.head(len(tasks_df) // 2)
        subset_ann = annotations_df[annotations_df["task_id"].isin(subset_tasks["task_id"])]
        wf_sub, ok_sub, _ = compute_backlog_waterfall(subset_ann, subset_tasks)
        assert ok_sub is True
        assert wf_sub["New Tasks Ingested"].sum() <= wf_full["New Tasks Ingested"].sum()
