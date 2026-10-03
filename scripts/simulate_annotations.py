"""
Operational Annotation Simulation Script
Generates realistic raw human annotation submissions across the synthetic task corpus.

Simulates:
- 4 distinct annotator profiles with realistic variance and cycle times:
  * ANNO-01: Junior auditor (higher variance, 91% accuracy, slightly slower)
  * ANNO-02: Standard auditor (95% accuracy, steady pace)
  * ANNO-03: Senior auditor (97% accuracy, fast pace)
  * ANNO-04: Quality Lead / Benchmark Specialist (99% accuracy)
- Controlled Edge-Case Injections to exercise all automated validation and rejection gates:
  * Missing conditional fields (e.g. OPEN_BOX without seal_condition)
  * Forbidden conditional fields (e.g. NEW with damage_type)
  * Speed anomalies (< 2.0s)
  * Duplicate submissions
  * Invalid categorical labels

All outputs are written into data/raw/ as immutable individual JSON payloads.
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
MANIFEST_FILE = DATA_DIR / "manifest_tasks.json"
GOLD_FILE = DATA_DIR / "gold" / "gold_annotations.json"

DEFAULT_SEED = 42


def simulate_annotation_run(num_submissions: int = 110, seed: int = DEFAULT_SEED):
    """Generate realistic raw submission files in data/raw/."""
    rng = random.Random(seed)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if not MANIFEST_FILE.exists():
        raise FileNotFoundError(f"Manifest file not found at {MANIFEST_FILE}. Run scripts/generate_dataset.py first.")

    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    # Load gold mappings to simulate realistic human noise
    gold_map = {}
    if GOLD_FILE.exists():
        with open(GOLD_FILE, "r", encoding="utf-8") as f:
            for g in json.load(f):
                gold_map[g["task_id"]] = g

    annotator_profiles = [
        {"id": "ANNO-01", "name": "Auditor Alpha", "acc": 0.91, "mean_time": 16.5, "speed_sigma": 4.0},
        {"id": "ANNO-02", "name": "Auditor Bravo", "acc": 0.95, "mean_time": 13.0, "speed_sigma": 3.0},
        {"id": "ANNO-03", "name": "Auditor Charlie", "acc": 0.97, "mean_time": 10.5, "speed_sigma": 2.5},
        {"id": "ANNO-04", "name": "Lead Specialist", "acc": 0.99, "mean_time": 8.0, "speed_sigma": 1.5},
    ]

    base_time = datetime.now(timezone.utc) - timedelta(days=5)
    generated_count = 0
    clean_count = 0
    injected_failures = 0

    # 1. Standard operational submissions
    for i in range(min(num_submissions, len(tasks))):
        task = tasks[i]
        task_id = task["task_id"]
        img_id = task["image_id"]
        annotator = rng.choice(annotator_profiles)

        # Baseline ground truth or realistic derivation
        gold_item = gold_map.get(task_id)
        if gold_item:
            true_cond = gold_item["ground_truth_condition"]
        else:
            # Deterministic category from seed & task index
            true_cond = ["NEW", "OPEN_BOX", "DAMAGED"][i % 3]

        # Determine if annotator makes an error
        is_correct = rng.random() < annotator["acc"]
        if is_correct:
            assigned_cond = true_cond
        else:
            choices = [c for c in ["NEW", "OPEN_BOX", "DAMAGED"] if c != true_cond]
            assigned_cond = rng.choice(choices)

        # Build valid secondary attributes matching SOP
        pkg_cond = None
        seal_cond = None
        dmg_type = None
        dmg_sev = None
        desc = None

        if assigned_cond == "OPEN_BOX":
            pkg_cond = rng.choice(["INTACT", "WORN", "MISSING"])
            seal_cond = rng.choice(["BROKEN", "MISSING", "RESEALED"])
        elif assigned_cond == "DAMAGED":
            dmg_type = rng.choice(["CRUSHED_BOX", "TEAR_PUNCTURE", "LIQUID_STAIN", "ITEM_DEFECT"])
            dmg_sev = rng.choice(["MINOR", "MODERATE", "SEVERE"])
            desc = f"Visual assessment confirms {dmg_type.lower()} defect of {dmg_sev.lower()} severity on carton."

        proc_time = max(1.2, round(rng.gauss(annotator["mean_time"], annotator["speed_sigma"]), 2))
        sub_time = base_time + timedelta(hours=i * 0.8, minutes=rng.randint(1, 45))

        payload = {
            "task_id": task_id,
            "image_id": img_id,
            "annotator_id": annotator["id"],
            "condition": assigned_cond,
            "packaging_condition": pkg_cond,
            "seal_condition": seal_cond,
            "damage_type": dmg_type,
            "damage_severity": dmg_sev,
            "description": desc,
            "annotation_timestamp": sub_time.isoformat(),
            "processing_time_seconds": proc_time,
            "schema_version": "1.0.0",
        }

        # Inject controlled failures on specific items to test validation gates
        if i == 7:  # Missing conditional field
            payload["packaging_condition"] = None
            injected_failures += 1
        elif i == 19:  # Unexpected secondary field on NEW
            payload["condition"] = "NEW"
            payload["damage_type"] = "CRUSHED_BOX"
            injected_failures += 1
        elif i == 31:  # Description too short
            payload["condition"] = "DAMAGED"
            payload["damage_type"] = "ITEM_DEFECT"
            payload["damage_severity"] = "MINOR"
            payload["description"] = "Dent"  # 4 chars < 10
            injected_failures += 1
        elif i == 45:  # Invalid categorical label
            payload["condition"] = "REFURBISHED_UNKNOWN"
            injected_failures += 1
        elif i == 60:  # Impossible processing time
            payload["processing_time_seconds"] = 0.05
            injected_failures += 1
        else:
            clean_count += 1

        ts_str = sub_time.strftime("%Y%m%dT%H%M%S")
        filename = f"{task_id}_{annotator['id']}_{ts_str}.json"
        with open(RAW_DIR / filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        generated_count += 1

    # Inject one duplicate submission
    dup_task = tasks[0]
    dup_filename = f"{dup_task['task_id']}_ANNO-01_DUPLICATE.json"
    dup_payload = {
        "task_id": dup_task["task_id"],
        "image_id": dup_task["image_id"],
        "annotator_id": "ANNO-01",
        "condition": "NEW",
        "packaging_condition": None,
        "seal_condition": None,
        "damage_type": None,
        "damage_severity": None,
        "description": None,
        "annotation_timestamp": datetime.now(timezone.utc).isoformat(),
        "processing_time_seconds": 14.2,
        "schema_version": "1.0.0",
    }
    with open(RAW_DIR / dup_filename, "w", encoding="utf-8") as f:
        json.dump(dup_payload, f, indent=2)
    generated_count += 1
    injected_failures += 1

    print(f"Generated {generated_count} raw submissions ({clean_count} nominal, {injected_failures} controlled anomalies/failures) in {RAW_DIR}")
    return generated_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate Human Annotation Operations")
    parser.add_argument("--count", type=int, default=110, help="Number of raw submissions to simulate")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed")
    args = parser.parse_args()

    simulate_annotation_run(args.count, args.seed)
