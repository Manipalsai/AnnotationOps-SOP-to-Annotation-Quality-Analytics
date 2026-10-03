"""
Shared pytest fixtures for AnnotationOps test suite.
Provides a self-contained SQLite test database built from the real schema
using deterministic seed data — no pre-generated files required.
Works on any clean CI runner without running pipeline scripts first.
"""

from __future__ import annotations

import random
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pipeline.database import DDL_STATEMENTS, DEFAULT_ANNOTATORS, DEFAULT_TARGETS, DEFAULT_OPERATIONAL_EVENTS

# ---------------------------------------------------------------------------
# Shared minimal test DB fixture
# ---------------------------------------------------------------------------

CATEGORIES = ["Electronics", "Clothing", "Home & Garden", "Books", "Toys"]
CONDITIONS = ["NEW", "OPEN_BOX", "DAMAGED"]
DIFFICULTIES = ["EASY", "MEDIUM", "HARD"]
STATUSES = ["COMPLETED", "PENDING", "REWORK", "ESCALATED"]

NUM_TASKS = 200
NUM_ANNOTATIONS = 180
NUM_GOLD = 40


def _build_test_db(conn: sqlite3.Connection) -> None:
    """Populate a connection with the full schema + deterministic seed data."""
    rng = random.Random(42)
    cursor = conn.cursor()

    # Schema
    for stmt in DDL_STATEMENTS.split(";"):
        s = stmt.strip()
        if s:
            cursor.execute(s)

    # Annotators (all 12)
    cursor.executemany(
        "INSERT OR IGNORE INTO annotators VALUES (?,?,?,?,?,?,1)",
        DEFAULT_ANNOTATORS,
    )

    # SLA targets
    cursor.executemany(
        "INSERT OR IGNORE INTO simulation_targets VALUES (?,?,?,?,?,?)",
        DEFAULT_TARGETS,
    )

    # Operational events
    cursor.executemany(
        "INSERT OR IGNORE INTO operational_events VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP)",
        DEFAULT_OPERATIONAL_EVENTS,
    )

    # Tasks
    task_ids = []
    for i in range(1, NUM_TASKS + 1):
        tid = f"TSK-{i:05d}"
        task_ids.append(tid)
        cat = rng.choice(CATEGORIES)
        diff = rng.choice(DIFFICULTIES)
        status = rng.choices(STATUSES, weights=[70, 15, 10, 5])[0]
        cursor.execute(
            """INSERT OR IGNORE INTO tasks
               (task_id, image_id, image_path, product_category, category_group,
                sku, difficulty, priority, status, synthetic, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,1,?)""",
            (
                tid, f"IMG-{i:05d}", f"data/images/img_{i:04d}.png",
                cat, "Category Group A", f"SKU-{i:05d}",
                diff, "NORMAL", status,
                (datetime(2026, 7, 6, tzinfo=timezone.utc) + timedelta(hours=i)).isoformat(),
            ),
        )

    # Gold annotations (first NUM_GOLD tasks)
    gold_task_ids = set()
    for i, tid in enumerate(task_ids[:NUM_GOLD]):
        cond = rng.choice(CONDITIONS)
        gold_task_ids.add(tid)
        cursor.execute(
            """INSERT OR IGNORE INTO gold_annotations
               (task_id, image_id, ground_truth_condition, difficulty, verified_by, synthetic)
               VALUES (?,?,?,?,?,1)""",
            (tid, f"IMG-{i+1:05d}", cond, rng.choice(DIFFICULTIES), "ANNO-12"),
        )

    # Annotations (validated events)
    annotator_ids = [a[0] for a in DEFAULT_ANNOTATORS]
    anno_ids_used = set()
    start = datetime(2026, 7, 6, 8, 0, 0, tzinfo=timezone.utc)

    for i in range(NUM_ANNOTATIONS):
        tid = rng.choice(task_ids[:NUM_TASKS])
        aid = rng.choice(annotator_ids)
        pair = (tid, aid)
        if pair in anno_ids_used:
            continue
        anno_ids_used.add(pair)

        cond = rng.choice(CONDITIONS)
        ts = (start + timedelta(minutes=i * 5)).isoformat()
        pkg = rng.choice(["INTACT", "WORN", "MISSING"]) if cond == "OPEN_BOX" else None
        seal = rng.choice(["BROKEN", "MISSING", "RESEALED"]) if cond == "OPEN_BOX" else None
        dmg_t = rng.choice(["CRUSHED_BOX", "TEAR_PUNCTURE", "LIQUID_STAIN"]) if cond == "DAMAGED" else None
        dmg_s = rng.choice(["MINOR", "MODERATE", "SEVERE"]) if cond == "DAMAGED" else None
        desc = "Visible damage observed on the outer packaging" if cond == "DAMAGED" else None
        dur = round(rng.uniform(4.0, 30.0), 2)
        anomaly = "WARN_SPEED_ANOMALY_FAST" if dur < 3.0 else None
        is_rework = 1 if rng.random() < 0.05 else 0
        is_esc = 1 if rng.random() < 0.03 else 0

        cursor.execute(
            """INSERT OR IGNORE INTO annotations
               (annotation_id, task_id, image_id, annotator_id, condition,
                packaging_condition, seal_condition, damage_type, damage_severity,
                description, annotation_timestamp, processing_time_seconds,
                anomaly_flag, is_rework, is_escalated, schema_version)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                f"ANN-{i:05d}", tid, f"IMG-{rng.randint(1,NUM_TASKS):05d}", aid,
                cond, pkg, seal, dmg_t, dmg_s, desc, ts, dur,
                anomaly, is_rework, is_esc, "1.0.0",
            ),
        )

    # Rejection audit (a few records)
    for i in range(15):
        tid = rng.choice(task_ids)
        aid = rng.choice(annotator_ids)
        cursor.execute(
            """INSERT OR IGNORE INTO rejection_audit
               (task_id, annotator_id, rejection_code, rejection_reason,
                validation_stage, raw_payload)
               VALUES (?,?,?,?,?,?)""",
            (
                tid, aid, "ERR_MISSING_REQUIRED_FIELD",
                "damage_type is required for DAMAGED condition",
                "STAGE_3_BUSINESS_RULES", "{}",
            ),
        )

    conn.commit()


@pytest.fixture(scope="session", autouse=True)
def ensure_dataset():
    """Ensure data/manifest_tasks.json and sample images exist for dataset tests."""
    manifest_path = Path("data/manifest_tasks.json")
    gold_path = Path("data/gold/gold_annotations.json")
    images_dir = Path("data/images")
    has_images = images_dir.exists() and any(images_dir.glob("*.png"))
    if not manifest_path.exists() or not gold_path.exists() or not has_images:
        from scripts.generate_dataset import generate_synthetic_dataset
        generate_synthetic_dataset("data", num_tasks=5000, seed=42)


@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory) -> Path:
    """
    Session-scoped fixture: creates a self-contained test SQLite warehouse.
    Built once per test session from deterministic seed data.
    No pipeline scripts or pre-generated files required.
    """
    db_file = tmp_path_factory.mktemp("db") / "test_annotationops.db"
    conn = sqlite3.connect(str(db_file))
    _build_test_db(conn)
    conn.close()
    return db_file


@pytest.fixture(scope="session")
def test_db_conn(test_db_path) -> sqlite3.Connection:
    """Session-scoped raw SQLite connection to the test warehouse."""
    conn = sqlite3.connect(str(test_db_path))
    yield conn
    conn.close()

