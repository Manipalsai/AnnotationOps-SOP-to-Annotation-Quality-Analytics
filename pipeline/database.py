"""
Relational Database Manager (SQLite) for AnnotationOps.
Implements the warehouse layer: schema creation, constraints, indexing,
and idempotent loading from clean processed and rejected audit sinks.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "annotationops.db"

DDL_STATEMENTS = """
-- 1. Tasks Table (Operational Queue)
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    image_id TEXT NOT NULL,
    image_path TEXT NOT NULL,
    product_category TEXT,
    sku TEXT,
    synthetic INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Annotators Table (Workforce Metadata)
CREATE TABLE IF NOT EXISTS annotators (
    annotator_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    active INTEGER DEFAULT 1
);

-- 3. Gold Annotations Table (Ground-Truth Benchmark)
CREATE TABLE IF NOT EXISTS gold_annotations (
    task_id TEXT PRIMARY KEY,
    image_id TEXT NOT NULL,
    ground_truth_condition TEXT NOT NULL,
    ground_truth_packaging_condition TEXT,
    ground_truth_seal_condition TEXT,
    ground_truth_damage_type TEXT,
    ground_truth_damage_severity TEXT,
    ground_truth_description TEXT,
    difficulty TEXT DEFAULT 'MEDIUM',
    verified_by TEXT,
    synthetic INTEGER DEFAULT 1,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- 4. Validated Annotations Table (Warehouse Core)
CREATE TABLE IF NOT EXISTS annotations (
    annotation_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    image_id TEXT NOT NULL,
    annotator_id TEXT NOT NULL,
    condition TEXT NOT NULL,
    packaging_condition TEXT,
    seal_condition TEXT,
    damage_type TEXT,
    damage_severity TEXT,
    description TEXT,
    annotation_timestamp TIMESTAMP NOT NULL,
    processing_time_seconds REAL NOT NULL,
    anomaly_flag TEXT,
    schema_version TEXT NOT NULL,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    FOREIGN KEY (annotator_id) REFERENCES annotators(annotator_id),
    UNIQUE(task_id, annotator_id)
);

-- 5. Rejection Audit Table (Data Quality Sink)
CREATE TABLE IF NOT EXISTS rejection_audit (
    rejection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    annotator_id TEXT,
    rejection_code TEXT NOT NULL,
    rejection_reason TEXT NOT NULL,
    validation_stage TEXT NOT NULL,
    raw_payload TEXT,
    rejected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, annotator_id, rejection_code, rejected_at)
);

-- Operational Performance Indexes
CREATE INDEX IF NOT EXISTS idx_annotations_task ON annotations(task_id);
CREATE INDEX IF NOT EXISTS idx_annotations_annotator ON annotations(annotator_id);
CREATE INDEX IF NOT EXISTS idx_annotations_timestamp ON annotations(annotation_timestamp);
CREATE INDEX IF NOT EXISTS idx_rejection_code ON rejection_audit(rejection_code);
CREATE INDEX IF NOT EXISTS idx_gold_task ON gold_annotations(task_id);
"""

DEFAULT_ANNOTATORS = [
    ("ANNO-01", "Auditor Alpha", "Junior Annotator"),
    ("ANNO-02", "Auditor Bravo", "Standard Annotator"),
    ("ANNO-03", "Auditor Charlie", "Senior Annotator"),
    ("ANNO-04", "Lead Specialist", "Quality Lead"),
]


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Initialize SQLite database with schema DDL and default annotator roster."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(DDL_STATEMENTS)

    # Seed annotators if empty
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM annotators;")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO annotators (annotator_id, display_name, role) VALUES (?, ?, ?);",
            DEFAULT_ANNOTATORS,
        )
        conn.commit()

    return conn


def load_tasks_and_gold(
    db_path: str | Path = DEFAULT_DB_PATH,
    manifest_file: str | Path = BASE_DIR / "data" / "manifest_tasks.json",
    gold_file: str | Path = BASE_DIR / "data" / "gold" / "gold_annotations.json",
) -> tuple[int, int]:
    """Load tasks manifest and gold benchmark set into SQLite warehouse."""
    conn = init_db(db_path)
    cursor = conn.cursor()

    tasks_loaded = 0
    gold_loaded = 0

    # 1. Load tasks manifest
    manifest_p = Path(manifest_file)
    if manifest_p.exists():
        with open(manifest_p, "r", encoding="utf-8") as f:
            tasks = json.load(f)
        for t in tasks:
            cursor.execute(
                """
                INSERT OR IGNORE INTO tasks (task_id, image_id, image_path, product_category, sku, synthetic)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    t["task_id"],
                    t["image_id"],
                    t["image_path"],
                    t.get("product_category"),
                    t.get("sku"),
                    1 if t.get("synthetic", True) else 0,
                ),
            )
            tasks_loaded += 1

    # 2. Load gold ground truth
    gold_p = Path(gold_file)
    if gold_p.exists():
        with open(gold_p, "r", encoding="utf-8") as f:
            gold = json.load(f)
        for g in gold:
            cursor.execute(
                """
                INSERT OR REPLACE INTO gold_annotations (
                    task_id, image_id, ground_truth_condition,
                    ground_truth_packaging_condition, ground_truth_seal_condition,
                    ground_truth_damage_type, ground_truth_damage_severity,
                    ground_truth_description, difficulty, verified_by, synthetic
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    g["task_id"],
                    g["image_id"],
                    g["ground_truth_condition"],
                    g.get("ground_truth_packaging_condition"),
                    g.get("ground_truth_seal_condition"),
                    g.get("ground_truth_damage_type"),
                    g.get("ground_truth_damage_severity"),
                    g.get("ground_truth_description"),
                    g.get("difficulty", "MEDIUM"),
                    g.get("verified_by", "Lead Quality Specialist"),
                    1 if g.get("synthetic", True) else 0,
                ),
            )
            gold_loaded += 1

    conn.commit()
    conn.close()
    return tasks_loaded, gold_loaded


def load_processed_and_rejected(
    db_path: str | Path = DEFAULT_DB_PATH,
    clean_file: str | Path = BASE_DIR / "data" / "processed" / "clean_annotations.jsonl",
    rejected_file: str | Path = BASE_DIR / "data" / "rejected" / "rejected_annotations.jsonl",
) -> tuple[int, int]:
    """Load validated clean annotations and rejected audit logs into warehouse."""
    conn = init_db(db_path)
    cursor = conn.cursor()

    clean_loaded = 0
    rejected_loaded = 0

    clean_p = Path(clean_file)
    if clean_p.exists():
        with open(clean_p, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                annotation_id = rec.get("annotation_id", str(uuid.uuid4()))
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO annotations (
                        annotation_id, task_id, image_id, annotator_id, condition,
                        packaging_condition, seal_condition, damage_type, damage_severity,
                        description, annotation_timestamp, processing_time_seconds,
                        anomaly_flag, schema_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        annotation_id,
                        rec["task_id"],
                        rec["image_id"],
                        rec["annotator_id"],
                        rec["condition"],
                        rec.get("packaging_condition"),
                        rec.get("seal_condition"),
                        rec.get("damage_type"),
                        rec.get("damage_severity"),
                        rec.get("description"),
                        rec["annotation_timestamp"],
                        rec["processing_time_seconds"],
                        rec.get("anomaly_flag"),
                        rec.get("schema_version", "1.0.0"),
                    ),
                )
                clean_loaded += 1

    rejected_p = Path(rejected_file)
    if rejected_p.exists():
        with open(rejected_p, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rej = json.loads(line)
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO rejection_audit (
                        task_id, annotator_id, rejection_code, rejection_reason,
                        validation_stage, raw_payload, rejected_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        rej.get("task_id"),
                        rej.get("annotator_id"),
                        rej["rejection_code"],
                        rej["rejection_reason"],
                        rej["validation_stage"],
                        json.dumps(rej.get("raw_payload", {})),
                        rej.get("timestamp"),
                    ),
                )
                rejected_loaded += 1

    conn.commit()
    conn.close()
    return clean_loaded, rejected_loaded
