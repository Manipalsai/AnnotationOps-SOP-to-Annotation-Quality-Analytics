"""
Historical Reprocessing and Backfill Script for AnnotationOps.
Allows operational leads to re-run validation and warehouse loading from raw immutable submissions,
useful when:
- SOP business rules or specification contracts are updated.
- Gold standard benchmarks are revised.
- Rebuilding warehouse tables following an outage or schema migration.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.run_pipeline import execute_pipeline
DATA_DIR = BASE_DIR / "data"
PROCESSED_FILE = DATA_DIR / "processed" / "clean_annotations.jsonl"
REJECTED_FILE = DATA_DIR / "rejected" / "rejected_annotations.jsonl"
DB_PATH = DATA_DIR / "annotationops.db"


def run_backfill(reset_warehouse: bool = True):
    """Purge derived warehouse tables and re-execute pipeline from raw sources."""
    print("================================================================================")
    print("ANNOTATIONOPS: HISTORICAL BACKFILL & REPROCESSING")
    print("================================================================================")

    if reset_warehouse:
        print("[Backfill] Purging derived files and SQLite warehouse for clean rebuild...")
        if PROCESSED_FILE.exists():
            PROCESSED_FILE.unlink()
            print(f"  - Removed {PROCESSED_FILE}")
        if REJECTED_FILE.exists():
            REJECTED_FILE.unlink()
            print(f"  - Removed {REJECTED_FILE}")
        if DB_PATH.exists():
            DB_PATH.unlink()
            print(f"  - Removed {DB_PATH}")
        ledger_file = DATA_DIR / "processed" / ".ingested_files.json"
        if ledger_file.exists():
            ledger_file.unlink()
            print(f"  - Removed {ledger_file}")

    # Re-run pipeline from raw submissions
    execute_pipeline(db_path=DB_PATH, verbose=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AnnotationOps Historical Backfill")
    parser.add_argument("--no-reset", action="store_true", help="Do not purge warehouse before backfill")
    args = parser.parse_args()

    run_backfill(reset_warehouse=not args.no_reset)
