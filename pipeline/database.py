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

TABLE_DDL = """
-- 1. Tasks Table (Operational Queue)
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    image_id TEXT NOT NULL,
    image_path TEXT NOT NULL,
    product_category TEXT,
    category_group TEXT,
    sku TEXT,
    difficulty TEXT DEFAULT 'MEDIUM',
    priority TEXT DEFAULT 'NORMAL',
    status TEXT DEFAULT 'PENDING',
    synthetic INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Annotators Table (Workforce Metadata)
CREATE TABLE IF NOT EXISTS annotators (
    annotator_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    team TEXT DEFAULT 'Team Alpha',
    shift TEXT DEFAULT 'Morning',
    experience_level TEXT DEFAULT 'Standard',
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
    is_rework INTEGER DEFAULT 0,
    is_escalated INTEGER DEFAULT 0,
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

-- 6. Operational Events Table (Synthetic Scenario Milestones)
CREATE TABLE IF NOT EXISTS operational_events (
    event_id TEXT PRIMARY KEY,
    week_number INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    impact_summary TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Simulation Targets Table (Operational SLA Baselines)
CREATE TABLE IF NOT EXISTS simulation_targets (
    metric_key TEXT PRIMARY KEY,
    metric_name TEXT NOT NULL,
    target_value REAL NOT NULL,
    unit TEXT NOT NULL,
    benchmark_type TEXT NOT NULL,
    description TEXT NOT NULL
);
"""

INDEX_DDL = """
-- Operational Performance Indexes
CREATE INDEX IF NOT EXISTS idx_annotations_task ON annotations(task_id);
CREATE INDEX IF NOT EXISTS idx_annotations_annotator ON annotations(annotator_id);
CREATE INDEX IF NOT EXISTS idx_annotations_timestamp ON annotations(annotation_timestamp);
CREATE INDEX IF NOT EXISTS idx_annotations_composite ON annotations(annotator_id, annotation_timestamp);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(product_category);
CREATE INDEX IF NOT EXISTS idx_tasks_difficulty ON tasks(difficulty);
CREATE INDEX IF NOT EXISTS idx_rejection_code ON rejection_audit(rejection_code);
CREATE INDEX IF NOT EXISTS idx_gold_task ON gold_annotations(task_id);
"""

DDL_STATEMENTS = TABLE_DDL + "\n" + INDEX_DDL

DEFAULT_ANNOTATORS = [
    ("ANNO-01", "Auditor Alpha", "Junior Annotator", "Team Alpha", "Morning", "0-6 months"),
    ("ANNO-02", "Auditor Bravo", "Standard Annotator", "Team Alpha", "Morning", "6-18 months"),
    ("ANNO-03", "Auditor Charlie", "Senior Annotator", "Team Alpha", "Evening", "2+ years"),
    ("ANNO-04", "Lead Specialist", "Quality Reviewer", "Quality Team", "Morning", "3+ years"),
    ("ANNO-05", "Auditor Delta", "Junior Annotator", "Team Beta", "Evening", "0-6 months"),
    ("ANNO-06", "Auditor Echo", "Standard Annotator", "Team Beta", "Morning", "6-18 months"),
    ("ANNO-07", "Auditor Foxtrot", "Standard Annotator", "Team Beta", "Evening", "6-18 months"),
    ("ANNO-08", "Auditor Golf", "Senior Annotator", "Team Beta", "Morning", "2+ years"),
    ("ANNO-09", "Auditor Hotel", "Senior Annotator", "Team Beta", "Evening", "2+ years"),
    ("ANNO-10", "Auditor India", "Quality Reviewer", "Quality Team", "Morning", "3+ years"),
    ("ANNO-11", "Auditor Juliet", "Quality Reviewer", "Quality Team", "Evening", "3+ years"),
    ("ANNO-12", "Master Specialist", "Lead Specialist", "Quality Team", "Morning", "4+ years"),
]

DEFAULT_TARGETS = [
    ("quality_accuracy_pct", "Quality Benchmark Accuracy", 95.0, "%", "MINIMUM", "Minimum acceptable ground-truth evaluation accuracy"),
    ("rejection_rate_pct", "Pipeline Rejection Rate", 3.0, "%", "MAXIMUM", "Maximum tolerated validation rejection threshold"),
    ("avg_processing_time_sec", "Cycle Time Pacing Target", 12.0, "s", "MAXIMUM", "Target average processing time per task unit"),
    ("cohens_kappa", "Inter-Annotator Agreement Kappa", 0.85, "score", "MINIMUM", "Statistical inter-rater reliability threshold"),
    ("completion_rate_pct", "Task Completion Velocity", 85.0, "%", "MINIMUM", "Target project completion rate threshold"),
]

DEFAULT_OPERATIONAL_EVENTS = [
    ("EVT-W05", 5, "VOLUME_SPIKE", "Peak Operational Surge", "Synthetic ingestion volume increased by 40% due to catalog expansion simulation.", "Higher backlog accumulation and increased pacing variance across junior annotators."),
    ("EVT-W07", 7, "QUALITY_DIP", "Edge-Case Ambiguity Influx", "Synthetic influx of high-difficulty packaging edge cases created labeling ambiguity.", "Temporary 4.2% dip in gold accuracy and increased conditional rule rejections."),
    ("EVT-W09", 9, "PROCESSING_TIME_INCREASE", "Enhanced Inspection Protocol", "Simulated introduction of rigorous damage description protocol.", "Average cycle time increased by 28% while annotators adapted to updated SOP criteria."),
    ("EVT-W10", 10, "PROCESS_RECOVERY", "Targeted Retraining & Tooling Fix", "Synthetic calibration workshop and UI prompt optimization implemented.", "Quality metrics recovered to 96.2% and processing pacing stabilized within target envelope."),
]


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Safely migrate existing tables if columns are missing."""
    cursor = conn.cursor()

    # Tasks columns
    cursor.execute("PRAGMA table_info(tasks);")
    task_cols = {row[1] for row in cursor.fetchall()}
    if "category_group" not in task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN category_group TEXT;")
    if "difficulty" not in task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN difficulty TEXT DEFAULT 'MEDIUM';")
    if "priority" not in task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN priority TEXT DEFAULT 'NORMAL';")
    if "status" not in task_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN status TEXT DEFAULT 'PENDING';")

    # Annotators columns
    cursor.execute("PRAGMA table_info(annotators);")
    anno_cols = {row[1] for row in cursor.fetchall()}
    if "team" not in anno_cols:
        cursor.execute("ALTER TABLE annotators ADD COLUMN team TEXT DEFAULT 'Team Alpha';")
    if "shift" not in anno_cols:
        cursor.execute("ALTER TABLE annotators ADD COLUMN shift TEXT DEFAULT 'Morning';")
    if "experience_level" not in anno_cols:
        cursor.execute("ALTER TABLE annotators ADD COLUMN experience_level TEXT DEFAULT 'Standard';")

    # Annotations columns
    cursor.execute("PRAGMA table_info(annotations);")
    annot_cols = {row[1] for row in cursor.fetchall()}
    if "is_rework" not in annot_cols:
        cursor.execute("ALTER TABLE annotations ADD COLUMN is_rework INTEGER DEFAULT 0;")
    if "is_escalated" not in annot_cols:
        cursor.execute("ALTER TABLE annotations ADD COLUMN is_escalated INTEGER DEFAULT 0;")

    conn.commit()


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Initialize SQLite database with schema DDL, migration safety, annotator roster, targets, and operational events."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(TABLE_DDL)
    _ensure_columns(conn)
    conn.executescript(INDEX_DDL)

    cursor = conn.cursor()

    # Seed annotators if empty or missing new columns
    cursor.execute("SELECT COUNT(*) FROM annotators;")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            """
            INSERT INTO annotators (annotator_id, display_name, role, team, shift, experience_level)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            DEFAULT_ANNOTATORS,
        )
        conn.commit()
    else:
        # Update annotators with detailed metadata if currently default
        for ann in DEFAULT_ANNOTATORS:
            cursor.execute(
                """
                UPDATE annotators
                SET display_name = ?, role = ?, team = ?, shift = ?, experience_level = ?
                WHERE annotator_id = ?;
                """,
                (ann[1], ann[2], ann[3], ann[4], ann[5], ann[0]),
            )
            # Insert if not exists
            cursor.execute(
                """
                INSERT OR IGNORE INTO annotators (annotator_id, display_name, role, team, shift, experience_level)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                ann,
            )
        conn.commit()

    # Seed simulation targets if empty
    cursor.execute("SELECT COUNT(*) FROM simulation_targets;")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            """
            INSERT INTO simulation_targets (metric_key, metric_name, target_value, unit, benchmark_type, description)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            DEFAULT_TARGETS,
        )
        conn.commit()

    # Seed operational events if empty
    cursor.execute("SELECT COUNT(*) FROM operational_events;")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            """
            INSERT INTO operational_events (event_id, week_number, event_type, title, description, impact_summary)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            DEFAULT_OPERATIONAL_EVENTS,
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
        task_rows = [
            (
                t["task_id"],
                t["image_id"],
                t["image_path"],
                t.get("product_category"),
                t.get("category_group", "General"),
                t.get("sku"),
                t.get("difficulty", "MEDIUM"),
                t.get("priority", "NORMAL"),
                t.get("status", "PENDING"),
                1 if t.get("synthetic", True) else 0,
            )
            for t in tasks
        ]
        cursor.executemany(
            """
            INSERT OR REPLACE INTO tasks (
                task_id, image_id, image_path, product_category, category_group,
                sku, difficulty, priority, status, synthetic
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            task_rows,
        )
        tasks_loaded = len(task_rows)

    # 2. Load gold ground truth
    gold_p = Path(gold_file)
    if gold_p.exists():
        with open(gold_p, "r", encoding="utf-8") as f:
            gold = json.load(f)
        gold_rows = [
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
            )
            for g in gold
        ]
        cursor.executemany(
            """
            INSERT OR REPLACE INTO gold_annotations (
                task_id, image_id, ground_truth_condition,
                ground_truth_packaging_condition, ground_truth_seal_condition,
                ground_truth_damage_type, ground_truth_damage_severity,
                ground_truth_description, difficulty, verified_by, synthetic
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            gold_rows,
        )
        gold_loaded = len(gold_rows)

    conn.commit()
    conn.close()
    return tasks_loaded, gold_loaded


def load_processed_and_rejected(
    db_path: str | Path = DEFAULT_DB_PATH,
    clean_file: str | Path = BASE_DIR / "data" / "processed" / "clean_annotations.jsonl",
    rejected_file: str | Path = BASE_DIR / "data" / "rejected" / "rejected_annotations.jsonl",
) -> tuple[int, int]:
    """Load validated clean annotations and rejected audit logs into warehouse with high-throughput batching."""
    conn = init_db(db_path)
    cursor = conn.cursor()

    clean_loaded = 0
    rejected_loaded = 0

    clean_p = Path(clean_file)
    if clean_p.exists():
        clean_rows = []
        with open(clean_p, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                annotation_id = rec.get("annotation_id", str(uuid.uuid4()))
                clean_rows.append(
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
                        1 if rec.get("is_rework") else 0,
                        1 if rec.get("is_escalated") else 0,
                        rec.get("schema_version", "1.0.0"),
                    )
                )

        if clean_rows:
            # Batch execute in chunks of 5000 for SQLite performance
            chunk_size = 5000
            for i in range(0, len(clean_rows), chunk_size):
                cursor.executemany(
                    """
                    INSERT OR IGNORE INTO annotations (
                        annotation_id, task_id, image_id, annotator_id, condition,
                        packaging_condition, seal_condition, damage_type, damage_severity,
                        description, annotation_timestamp, processing_time_seconds,
                        anomaly_flag, is_rework, is_escalated, schema_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    clean_rows[i : i + chunk_size],
                )
            clean_loaded = len(clean_rows)

        # Update tasks operational status
        cursor.execute(
            """
            UPDATE tasks 
            SET status = 'COMPLETED'
            WHERE task_id IN (
                SELECT DISTINCT task_id FROM annotations WHERE is_rework = 0 AND is_escalated = 0
            );
            """
        )
        cursor.execute(
            """
            UPDATE tasks 
            SET status = 'REWORK'
            WHERE task_id IN (
                SELECT DISTINCT task_id FROM annotations WHERE is_rework = 1
            );
            """
        )
        cursor.execute(
            """
            UPDATE tasks 
            SET status = 'ESCALATED'
            WHERE task_id IN (
                SELECT DISTINCT task_id FROM annotations WHERE is_escalated = 1
            );
            """
        )

    rejected_p = Path(rejected_file)
    if rejected_p.exists():
        rej_rows = []
        with open(rejected_p, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rej = json.loads(line)
                rej_rows.append(
                    (
                        rej.get("task_id"),
                        rej.get("annotator_id"),
                        rej["rejection_code"],
                        rej["rejection_reason"],
                        rej["validation_stage"],
                        json.dumps(rej.get("raw_payload", {})),
                        rej.get("timestamp"),
                    )
                )

        if rej_rows:
            chunk_size = 5000
            for i in range(0, len(rej_rows), chunk_size):
                cursor.executemany(
                    """
                    INSERT OR IGNORE INTO rejection_audit (
                        task_id, annotator_id, rejection_code, rejection_reason,
                        validation_stage, raw_payload, rejected_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    rej_rows[i : i + chunk_size],
                )
            rejected_loaded = len(rej_rows)

    conn.commit()
    conn.close()
    return clean_loaded, rejected_loaded
