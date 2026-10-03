"""
AnnotationOps Self-Bootstrapping Engine (pipeline/bootstrap.py).
================================================================
Provides zero-configuration, deterministic self-bootstrapping for:
- Fresh Git clones
- Streamlit Community Cloud deployments (/mount/src/...)
- Docker containers
- Clean CI/CD runners

Determines whether data/annotationops.db exists and is fully populated with all
required tables. If absent or invalid, deterministically generates the synthetic
workload (seed=42, 5,000 assets, ~25K annotations, 12 annotators, 400 gold items,
rejection audit log, operational events, and SLA targets) and populates the warehouse.

Reuses existing pipeline modules:
- scripts.generate_dataset.generate_synthetic_dataset
- scripts.simulate_annotations.simulate_enterprise_operations
- pipeline.database (init_db, load_tasks_and_gold, load_processed_and_rejected)
- scripts.run_pipeline.run_sql_quality_audit
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path
from typing import Callable, Optional

# Robust project base directory resolution (repository-relative)
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pipeline.database import (
    DEFAULT_DB_PATH,
    init_db,
    load_processed_and_rejected,
    load_tasks_and_gold,
)
from scripts.generate_dataset import generate_synthetic_dataset
from scripts.run_pipeline import run_sql_quality_audit
from scripts.simulate_annotations import simulate_enterprise_operations

logger = logging.getLogger("annotationops.bootstrap")

# Minimum expected record counts per required warehouse table across all 5 dashboard views
REQUIRED_TABLES: dict[str, int] = {
    "tasks": 5000,
    "annotators": 12,
    "gold_annotations": 400,
    "annotations": 20000,       # ~25,000 clean annotations expected
    "rejection_audit": 500,     # ~1,000 firewall rejections expected
    "operational_events": 4,    # 4 historical milestones
    "simulation_targets": 5,    # 5 SLA targets
}


class BootstrapError(Exception):
    """Raised when an automated pipeline bootstrap stage fails."""

    def __init__(self, stage: str, message: str):
        self.stage = stage
        self.message = message
        super().__init__(f"[{stage}] {message}")


def verify_database_integrity(
    db_path: Path | str = DEFAULT_DB_PATH,
) -> tuple[bool, str, dict[str, int]]:
    """
    Verify that SQLite warehouse exists and contains all required tables with records.

    Returns:
        tuple[bool, str, dict[str, int]]: (is_valid, status_message, table_counts)
    """
    target = Path(db_path)
    if not target.exists():
        return False, f"Database file does not exist at {target}", {}

    if target.stat().st_size == 0:
        return False, f"Database file at {target} is empty (0 bytes)", {}

    table_counts: dict[str, int] = {}
    try:
        conn = sqlite3.connect(str(target))
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = {row[0] for row in cursor.fetchall()}

        for table, min_expected in REQUIRED_TABLES.items():
            if table not in existing_tables:
                conn.close()
                return False, f"Required table '{table}' missing from database schema.", table_counts

            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            count = cursor.fetchone()[0]
            table_counts[table] = count

            if count < min_expected:
                conn.close()
                return (
                    False,
                    f"Table '{table}' has insufficient records ({count:,} < minimum {min_expected:,}).",
                    table_counts,
                )

        conn.close()
        return True, "All required tables and baseline records verified successfully.", table_counts

    except Exception as exc:
        return False, f"Database integrity check failed with error: {exc}", table_counts


def bootstrap_warehouse(
    db_path: Path | str = DEFAULT_DB_PATH,
    seed: int = 42,
    num_assets: int = 5000,
    num_annotations: int = 25000,
    force: bool = False,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> tuple[bool, str]:
    """
    Deterministically bootstrap the complete synthetic dataset, validation firewall,
    and SQLite analytics warehouse.

    Stages:
      1. Initialize directory structures (data/raw, data/processed, etc.)
      2. Generate deterministic synthetic asset catalog and gold benchmark (seed=42)
      3. Simulate 12-annotator enterprise operations (~25K events, rejections, scenario events)
      4. Initialize SQLite relational schema, seed annotators/targets, and load tables
      5. Run SQL quality audit and programmatically verify all required tables

    Returns:
        tuple[bool, str]: (success, status_description)
    """
    target_db = Path(db_path)

    def _notify(stage_name: str, pct: float):
        logger.info(f"[{pct*100:0.0f}%] {stage_name}")
        if progress_callback:
            progress_callback(stage_name, pct)

    # Short-circuit if already valid and not forcing rebuild
    if not force:
        is_valid, msg, counts = verify_database_integrity(target_db)
        if is_valid:
            _notify("Database verified and ready.", 1.0)
            return True, f"Warehouse already valid: {msg}"

    data_dir = target_db.parent if target_db.parent.name == "data" else BASE_DIR / "data"

    # Stage 1: Directory initialization
    current_stage = "Stage 1/5: Initializing required directory structure"
    try:
        _notify(current_stage, 0.05)
        for sub in ["raw", "processed", "rejected", "gold", "images"]:
            (data_dir / sub).mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise BootstrapError(current_stage, f"Failed creating directories: {exc}") from exc

    # Stage 2: Synthetic dataset generation
    current_stage = "Stage 2/5: Generating synthetic dataset & gold benchmark (seed=42)"
    try:
        _notify(current_stage, 0.20)
        n_tasks, n_gold = generate_synthetic_dataset(
            output_dir=str(data_dir),
            num_assets=num_assets,
            gold_ratio=0.08,
            num_image_samples=200,
            seed=seed,
        )
        logger.info(f"Generated {n_tasks:,} tasks, {n_gold:,} gold benchmarks.")
    except Exception as exc:
        raise BootstrapError(current_stage, f"Dataset generation failed: {exc}") from exc

    # Stage 3: Human operations simulation
    current_stage = "Stage 3/5: Simulating 12-annotator operations & rejection audit"
    try:
        _notify(current_stage, 0.45)
        sim_res = simulate_enterprise_operations(
            target_clean=num_annotations,
            seed=seed,
            num_raw_samples=60,
            data_dir=data_dir,
        )
        logger.info(f"Simulated {sim_res['clean_count']:,} clean, {sim_res['rejected_count']:,} rejections.")
    except Exception as exc:
        raise BootstrapError(current_stage, f"Operations simulation failed: {exc}") from exc

    # Stage 4: Relational warehouse loading
    current_stage = "Stage 4/5: Initializing SQLite warehouse and loading tables"
    try:
        _notify(current_stage, 0.70)
        init_db(target_db)
        tasks_loaded, gold_loaded = load_tasks_and_gold(
            db_path=target_db,
            manifest_file=data_dir / "manifest_tasks.json",
            gold_file=data_dir / "gold" / "gold_annotations.json",
        )
        clean_loaded, rej_loaded = load_processed_and_rejected(
            db_path=target_db,
            clean_file=data_dir / "processed" / "clean_annotations.jsonl",
            rejected_file=data_dir / "rejected" / "rejected_annotations.jsonl",
        )
        logger.info(
            f"Loaded warehouse: {tasks_loaded:,} tasks, {gold_loaded:,} gold, "
            f"{clean_loaded:,} clean, {rej_loaded:,} rejections."
        )
    except Exception as exc:
        raise BootstrapError(current_stage, f"Warehouse loading failed: {exc}") from exc

    # Stage 5: Integrity verification & SQL quality gate
    current_stage = "Stage 5/5: Running SQL quality audit & verifying all dashboard tables"
    try:
        _notify(current_stage, 0.90)
        audit_res = run_sql_quality_audit(target_db)
        violations = sum(audit_res.values())
        if violations > 0:
            raise BootstrapError(
                current_stage,
                f"SQL quality gate detected {violations} integrity violations: {audit_res}",
            )

        is_valid, msg, counts = verify_database_integrity(target_db)
        if not is_valid:
            raise BootstrapError(current_stage, f"Post-creation table verification failed: {msg}")

        _notify("Warehouse ready and verified.", 1.0)
        return True, f"Warehouse successfully bootstrapped: {counts}"

    except BootstrapError:
        raise
    except Exception as exc:
        raise BootstrapError(current_stage, f"Integrity check failed: {exc}") from exc
