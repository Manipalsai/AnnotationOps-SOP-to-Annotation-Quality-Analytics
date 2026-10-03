"""
End-to-End Integration Tests for Ingestion, Validation, Warehouse & Quality Pipeline.
Verifies:
- End-to-end processing of controlled raw submissions
- Rejection handling and audit trail creation
- Relational schema constraints and SQL data quality assertions
- Statistical metric computation accuracy and idempotency
"""

import json
from pathlib import Path
import pytest

from pipeline.database import init_db, load_tasks_and_gold, load_processed_and_rejected
from pipeline.metrics import compute_operations_kpis, compute_quality_kpis, compute_annotator_kpis
from pipeline.validate import process_raw_directory, validate_raw_payload
from scripts.run_pipeline import run_sql_quality_audit


@pytest.fixture
def isolated_pipeline_env(tmp_path):
    """Create a completely isolated directory environment for end-to-end testing."""
    raw_dir = tmp_path / "raw"
    proc_dir = tmp_path / "processed"
    rej_dir = tmp_path / "rejected"
    gold_dir = tmp_path / "gold"
    db_file = tmp_path / "test_ops.db"

    raw_dir.mkdir()
    proc_dir.mkdir()
    rej_dir.mkdir()
    gold_dir.mkdir()

    # Create dummy tasks manifest
    manifest_file = tmp_path / "manifest_tasks.json"
    manifest = [
        {"task_id": "T-01", "image_id": "img1.png", "image_path": "data/images/img1.png", "product_category": "Audio", "sku": "SKU-1"},
        {"task_id": "T-02", "image_id": "img2.png", "image_path": "data/images/img2.png", "product_category": "Tech", "sku": "SKU-2"},
        {"task_id": "T-03", "image_id": "img3.png", "image_path": "data/images/img3.png", "product_category": "Wearables", "sku": "SKU-3"},
    ]
    with open(manifest_file, "w") as f:
        json.dump(manifest, f)

    # Create dummy gold benchmark
    gold_file = gold_dir / "gold_annotations.json"
    gold = [
        {"task_id": "T-01", "image_id": "img1.png", "ground_truth_condition": "NEW", "difficulty": "EASY"},
        {"task_id": "T-02", "image_id": "img2.png", "ground_truth_condition": "DAMAGED", "ground_truth_damage_type": "CRUSHED_BOX", "ground_truth_damage_severity": "MINOR", "ground_truth_description": "Dent on corner", "difficulty": "MEDIUM"},
    ]
    with open(gold_file, "w") as f:
        json.dump(gold, f)

    return {
        "raw_dir": raw_dir,
        "proc_file": proc_dir / "clean.jsonl",
        "rej_file": rej_dir / "rejected.jsonl",
        "manifest_file": manifest_file,
        "gold_file": gold_file,
        "db_file": db_file,
    }


def test_pipeline_valid_and_rejected_flow(isolated_pipeline_env):
    """Test that valid records pass into clean sink and invalid land in rejection sink with reason codes."""
    env = isolated_pipeline_env

    # 1. Valid NEW submission
    rec_valid = {
        "task_id": "T-01",
        "image_id": "img1.png",
        "annotator_id": "ANNO-01",
        "condition": "NEW",
        "packaging_condition": None,
        "seal_condition": None,
        "damage_type": None,
        "damage_severity": None,
        "description": None,
        "annotation_timestamp": "2026-10-01T10:00:00Z",
        "processing_time_seconds": 12.0,
        "schema_version": "1.0.0",
    }
    with open(env["raw_dir"] / "valid_01.json", "w") as f:
        json.dump(rec_valid, f)

    # 2. Invalid conditional submission (OPEN_BOX missing seal_condition)
    rec_invalid_cond = {
        "task_id": "T-02",
        "image_id": "img2.png",
        "annotator_id": "ANNO-02",
        "condition": "OPEN_BOX",
        "packaging_condition": "INTACT",
        # missing seal_condition
        "annotation_timestamp": "2026-10-01T10:05:00Z",
        "processing_time_seconds": 15.0,
        "schema_version": "1.0.0",
    }
    with open(env["raw_dir"] / "invalid_02.json", "w") as f:
        json.dump(rec_invalid_cond, f)

    # 3. Invalid impossible processing time
    rec_invalid_time = {
        "task_id": "T-03",
        "image_id": "img3.png",
        "annotator_id": "ANNO-03",
        "condition": "NEW",
        "annotation_timestamp": "2026-10-01T10:10:00Z",
        "processing_time_seconds": 0.01,  # physically impossible
        "schema_version": "1.0.0",
    }
    with open(env["raw_dir"] / "invalid_03.json", "w") as f:
        json.dump(rec_invalid_time, f)

    # Execute processing
    scanned, clean_cnt, rej_cnt = process_raw_directory(
        raw_dir=env["raw_dir"],
        processed_out=env["proc_file"],
        rejected_out=env["rej_file"],
    )

    assert scanned == 3
    assert clean_cnt == 1
    assert rej_cnt == 2

    # Verify clean sink content
    with open(env["proc_file"]) as f:
        clean_lines = [json.loads(line) for line in f if line.strip()]
    assert len(clean_lines) == 1
    assert clean_lines[0]["task_id"] == "T-01"

    # Verify rejection sink content and codes
    with open(env["rej_file"]) as f:
        rej_lines = [json.loads(line) for line in f if line.strip()]
    assert len(rej_lines) == 2
    rej_codes = [r["rejection_code"] for r in rej_lines]
    assert "ERR_CONDITIONAL_FIELD_MISSING" in rej_codes
    assert "ERR_IMPOSSIBLE_TIME" in rej_codes


def test_pipeline_database_loading_and_sql_audit(isolated_pipeline_env):
    """Test database loading and verify 0 violations on SQL quality checks."""
    env = isolated_pipeline_env

    # Write one clean and one rejected record
    with open(env["proc_file"], "w") as f:
        f.write(json.dumps({
            "task_id": "T-01",
            "image_id": "img1.png",
            "annotator_id": "ANNO-01",
            "condition": "NEW",
            "packaging_condition": None,
            "seal_condition": None,
            "damage_type": None,
            "damage_severity": None,
            "description": None,
            "annotation_timestamp": "2026-10-01T10:00:00Z",
            "processing_time_seconds": 12.0,
            "schema_version": "1.0.0",
        }) + "\n")

    with open(env["rej_file"], "w") as f:
        f.write(json.dumps({
            "task_id": "T-02",
            "annotator_id": "ANNO-02",
            "rejection_code": "ERR_CONDITIONAL_FIELD_MISSING",
            "rejection_reason": "seal_condition required",
            "validation_stage": "STAGE_3_CONDITIONAL_RULES",
            "raw_payload": {},
            "timestamp": "2026-10-01T10:05:00Z",
        }) + "\n")

    # Load DB
    init_db(env["db_file"])
    load_tasks_and_gold(env["db_file"], manifest_file=env["manifest_file"], gold_file=env["gold_file"])
    clean_loaded, rej_loaded = load_processed_and_rejected(env["db_file"], clean_file=env["proc_file"], rejected_file=env["rej_file"])

    assert clean_loaded == 1
    assert rej_loaded == 1

    # Run SQL Quality checks
    dq_results = run_sql_quality_audit(env["db_file"])
    assert dq_results["duplicate_count"] == 0
    assert dq_results["null_count"] == 0
    assert dq_results["invalid_label_count"] == 0
    assert dq_results["conditional_violations"] == 0

    # Calculate metrics
    ops = compute_operations_kpis(env["db_file"])
    assert ops["total_tasks"] == 3
    assert ops["completed_tasks"] == 1
    assert ops["pending_backlog"] == 2
    assert ops["rejection_rate_pct"] == 50.0  # 1 valid, 1 rejected

    qual = compute_quality_kpis(env["db_file"])
    assert qual["total_gold_evaluated"] == 1
    assert qual["accuracy_pct"] == 100.0  # T-01 was NEW in gold and annotated NEW
