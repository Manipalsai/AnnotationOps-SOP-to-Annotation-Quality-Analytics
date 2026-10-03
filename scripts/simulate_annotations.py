"""
Enterprise Annotation Operations Simulation Script (AnnotationOps v2)
Generates high-scale, realistic, deterministic synthetic annotation workloads (seed=42).

Simulates:
- 12 synthetic annotators across 2 operational shifts, 2 teams, and 4 seniority tiers
- 12 weeks of historical operations (84 days) with realistic weekday/weekend pacing
- 4 controlled operational scenario events:
  * Week 5: Volume Spike (+40% task surge)
  * Week 7: Quality Dip (~4.5% accuracy drop from edge-case ambiguity)
  * Week 9: Processing Time Increase (+28% duration from enhanced damage protocol)
  * Week 10: Process Recovery (calibration workshop and workflow stabilization)
- Realistic multi-rater agreement (~1,500 multi-annotated tasks for Cohen's Kappa)
- Difficulty correlation: HARD tasks take 30% longer and have 5% lower accuracy
- Controlled rejection events (schema violations, conditional rule violations, pacing anomalies)
- Direct JSONL stream generation for enterprise scale (~25,000+ annotations in <15 seconds)

DISCLOSURE: Dataset is completely synthetic and simulated for portfolio demonstration.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from schemas.models import (
    AnnotationRecord,
    PrimaryCondition,
    PackagingCondition,
    SealCondition,
    DamageType,
    DamageSeverity,
    RejectionCode,
    RejectedRecord,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_FILE = DATA_DIR / "processed" / "clean_annotations.jsonl"
REJECTED_FILE = DATA_DIR / "rejected" / "rejected_annotations.jsonl"
MANIFEST_FILE = DATA_DIR / "manifest_tasks.json"
GOLD_FILE = DATA_DIR / "gold" / "gold_annotations.json"

DEFAULT_SEED = 42

ANNOTATOR_ROSTER = [
    {
        "id": "ANNO-01",
        "name": "Auditor Alpha",
        "role": "Junior Annotator",
        "team": "Team Alpha",
        "shift": "Morning",
        "exp": "0-6 months",
        "base_acc": 0.910,
        "mean_time": 15.5,
        "speed_sigma": 3.0,
    },
    {
        "id": "ANNO-02",
        "name": "Auditor Bravo",
        "role": "Standard Annotator",
        "team": "Team Alpha",
        "shift": "Morning",
        "exp": "6-18 months",
        "base_acc": 0.942,
        "mean_time": 12.8,
        "speed_sigma": 2.4,
    },
    {
        "id": "ANNO-03",
        "name": "Auditor Charlie",
        "role": "Senior Annotator",
        "team": "Team Alpha",
        "shift": "Evening",
        "exp": "2+ years",
        "base_acc": 0.965,
        "mean_time": 10.4,
        "speed_sigma": 2.0,
    },
    {
        "id": "ANNO-04",
        "name": "Lead Specialist",
        "role": "Quality Reviewer",
        "team": "Quality Team",
        "shift": "Morning",
        "exp": "3+ years",
        "base_acc": 0.985,
        "mean_time": 8.2,
        "speed_sigma": 1.5,
    },
    {
        "id": "ANNO-05",
        "name": "Auditor Delta",
        "role": "Junior Annotator",
        "team": "Team Beta",
        "shift": "Evening",
        "exp": "0-6 months",
        "base_acc": 0.898,
        "mean_time": 16.2,
        "speed_sigma": 3.2,
    },
    {
        "id": "ANNO-06",
        "name": "Auditor Echo",
        "role": "Standard Annotator",
        "team": "Team Beta",
        "shift": "Morning",
        "exp": "6-18 months",
        "base_acc": 0.938,
        "mean_time": 13.0,
        "speed_sigma": 2.5,
    },
    {
        "id": "ANNO-07",
        "name": "Auditor Foxtrot",
        "role": "Standard Annotator",
        "team": "Team Beta",
        "shift": "Evening",
        "exp": "6-18 months",
        "base_acc": 0.948,
        "mean_time": 12.2,
        "speed_sigma": 2.3,
    },
    {
        "id": "ANNO-08",
        "name": "Auditor Golf",
        "role": "Senior Annotator",
        "team": "Team Beta",
        "shift": "Morning",
        "exp": "2+ years",
        "base_acc": 0.970,
        "mean_time": 9.9,
        "speed_sigma": 1.8,
    },
    {
        "id": "ANNO-09",
        "name": "Auditor Hotel",
        "role": "Senior Annotator",
        "team": "Team Beta",
        "shift": "Evening",
        "exp": "2+ years",
        "base_acc": 0.962,
        "mean_time": 10.6,
        "speed_sigma": 2.1,
    },
    {
        "id": "ANNO-10",
        "name": "Auditor India",
        "role": "Quality Reviewer",
        "team": "Quality Team",
        "shift": "Morning",
        "exp": "3+ years",
        "base_acc": 0.982,
        "mean_time": 8.5,
        "speed_sigma": 1.6,
    },
    {
        "id": "ANNO-11",
        "name": "Auditor Juliet",
        "role": "Quality Reviewer",
        "team": "Quality Team",
        "shift": "Evening",
        "exp": "3+ years",
        "base_acc": 0.986,
        "mean_time": 8.0,
        "speed_sigma": 1.4,
    },
    {
        "id": "ANNO-12",
        "name": "Master Specialist",
        "role": "Lead Specialist",
        "team": "Quality Team",
        "shift": "Morning",
        "exp": "4+ years",
        "base_acc": 0.992,
        "mean_time": 7.4,
        "speed_sigma": 1.2,
    },
]


def _build_valid_payload(
    task: dict[str, Any],
    annotator: dict[str, Any],
    true_cond: str,
    timestamp: datetime,
    is_correct: bool,
    mean_duration: float,
    speed_sigma: float,
    rng: random.Random,
    is_rework: bool = False,
    is_escalated: bool = False,
) -> dict[str, Any]:
    """Construct an SOP-compliant annotation record payload."""
    if is_correct:
        assigned_cond = true_cond
    else:
        choices = [c for c in ["NEW", "OPEN_BOX", "DAMAGED"] if c != true_cond]
        assigned_cond = rng.choice(choices)

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

    duration = max(2.1, round(rng.gauss(mean_duration, speed_sigma), 2))
    anomaly_flag = "WARN_SPEED_ANOMALY_FAST" if duration < 3.0 else None

    return {
        "annotation_id": str(uuid.UUID(int=rng.getrandbits(128), version=4)),
        "task_id": task["task_id"],
        "image_id": task["image_id"],
        "annotator_id": annotator["id"],
        "condition": assigned_cond,
        "packaging_condition": pkg_cond,
        "seal_condition": seal_cond,
        "damage_type": dmg_type,
        "damage_severity": dmg_sev,
        "description": desc,
        "annotation_timestamp": timestamp.isoformat(),
        "processing_time_seconds": duration,
        "anomaly_flag": anomaly_flag,
        "is_rework": is_rework,
        "is_escalated": is_escalated,
        "schema_version": "1.0.0",
    }


def simulate_enterprise_operations(
    target_clean: int = 25000,
    seed: int = DEFAULT_SEED,
    num_raw_samples: int = 60,
    data_dir: Path | str | None = None,
) -> dict[str, int]:
    """
    Run full 12-week operational simulation.
    Produces clean annotations JSONL, rejected audit JSONL, and a sample of raw JSON files.
    """
    rng = random.Random(seed)
    base_data = Path(data_dir) if data_dir is not None else DATA_DIR
    processed_file = base_data / "processed" / "clean_annotations.jsonl"
    rejected_file = base_data / "rejected" / "rejected_annotations.jsonl"
    manifest_file = base_data / "manifest_tasks.json"
    gold_file = base_data / "gold" / "gold_annotations.json"
    raw_dir = base_data / "raw"

    processed_file.parent.mkdir(parents=True, exist_ok=True)
    rejected_file.parent.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    if not manifest_file.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_file}. Run generate_dataset.py first.")

    with open(manifest_file, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    gold_map = {}
    if gold_file.exists():
        with open(gold_file, "r", encoding="utf-8") as f:
            for g in json.load(f):
                gold_map[g["task_id"]] = g

    # 12-week timeline: 84 operational days anchored to 2026-07-06 through 2026-09-27
    start_time = datetime(2026, 7, 6, 8, 0, 0, tzinfo=timezone.utc)
    total_days = 84

    # Pre-plan daily target clean volume
    daily_targets = []
    for day in range(total_days):
        week_num = (day // 7) + 1
        dow = day % 7  # 0=Mon, ..., 6=Sun
        is_weekend = dow >= 5

        # Base volume
        base = 110 if is_weekend else 360

        # Scenario modifiers
        if week_num == 5:
            base = int(base * 1.40)  # Week 5 Volume Surge

        daily_targets.append((day, week_num, dow, base))

    sum_targets = sum(t[3] for t in daily_targets)
    scale_factor = target_clean / sum_targets

    # Pre-assign tasks to ensure multi-rater distribution
    # ~3,200 tasks get 1 rater, ~1,100 tasks get 2 raters, ~400 tasks get 3 raters
    task_assignments: list[tuple[dict[str, Any], list[dict[str, Any]], bool, bool]] = []
    available_tasks = list(tasks)
    rng.shuffle(available_tasks)

    # 300 tasks remain pending in backlog
    actionable_tasks = available_tasks[:-300] if len(available_tasks) > 300 else available_tasks
    num_actionable = len(actionable_tasks)

    # Dynamically distribute raters across actionable tasks to reach target_clean
    avg_k = max(1, min(10, int(round(target_clean / num_actionable))))

    event_queue: list[tuple[dict[str, Any], dict[str, Any], bool, bool]] = []
    used_pairs: set[tuple[str, str]] = set()

    for idx, t in enumerate(actionable_tasks):
        if idx % 4 == 0:
            k = max(1, avg_k - 2)
        elif idx % 4 == 1:
            k = max(1, avg_k - 1)
        elif idx % 4 == 2:
            k = avg_k
        else:
            k = min(11, avg_k + 2)

        is_rework = (idx % 18 == 0)
        is_escalated = (idx % 45 == 0)

        raters = rng.sample(ANNOTATOR_ROSTER, min(k, len(ANNOTATOR_ROSTER)))
        for r in raters:
            pair = (t["task_id"], r["id"])
            if pair not in used_pairs:
                used_pairs.add(pair)
                event_queue.append((t, r, is_rework, is_escalated))

    # Fill up to target_clean if needed with unused distinct (task, annotator) pairs
    if len(event_queue) < target_clean:
        for t in actionable_tasks:
            if len(event_queue) >= target_clean:
                break
            for r in ANNOTATOR_ROSTER:
                pair = (t["task_id"], r["id"])
                if pair not in used_pairs:
                    used_pairs.add(pair)
                    event_queue.append((t, r, False, False))
                    if len(event_queue) >= target_clean:
                        break

    if len(event_queue) > target_clean:
        event_queue = event_queue[:target_clean]

    rng.shuffle(event_queue)

    print(f"[Simulation] Generating {len(event_queue):,} annotations across 12 operational weeks (seed={seed})...")

    clean_records: list[dict[str, Any]] = []
    rejected_records: list[dict[str, Any]] = []
    raw_sample_written = 0

    event_cursor = 0
    total_events = len(event_queue)

    for day, week_num, dow, base_vol in daily_targets:
        target_today = int(round(base_vol * scale_factor))
        day_date = start_time + timedelta(days=day)

        # Scenario parameters for this week
        acc_modifier = 0.0
        time_modifier = 1.0
        rejection_prob = 0.035

        if week_num == 7:
            # Week 7 Quality Dip & Rejection Influx
            acc_modifier = -0.045
            rejection_prob = 0.065
        elif week_num == 9:
            # Week 9 Cycle Time Increase
            time_modifier = 1.28
        elif week_num >= 10:
            # Recovery & Process Stabilization
            acc_modifier = +0.010
            time_modifier = 0.95
            rejection_prob = 0.025

        # Process clean events for this day
        day_events_done = 0
        while day_events_done < target_today and event_cursor < total_events:
            t, annotator, is_rework, is_escalated = event_queue[event_cursor]
            event_cursor += 1

            # Determine true condition
            gold = gold_map.get(t["task_id"])
            if gold:
                true_cond = gold["ground_truth_condition"]
            else:
                # Deterministic derived condition
                true_cond = ["NEW", "OPEN_BOX", "DAMAGED"][event_cursor % 3]

            # Adjust annotator accuracy by difficulty
            diff = t.get("difficulty", "MEDIUM")
            diff_adj = 0.025 if diff == "EASY" else (-0.050 if diff == "HARD" else 0.0)
            effective_acc = max(0.70, min(0.999, annotator["base_acc"] + acc_modifier + diff_adj))

            is_correct = rng.random() < effective_acc

            # Adjust processing time by difficulty
            diff_time_mult = 0.85 if diff == "EASY" else (1.30 if diff == "HARD" else 1.0)
            mean_time = annotator["mean_time"] * time_modifier * diff_time_mult
            sigma = annotator["speed_sigma"] * 0.9

            # Timestamp within work shift (8:00 to 18:00)
            sec_offset = rng.randint(0, 10 * 3600)
            sub_ts = day_date + timedelta(seconds=sec_offset)

            clean_payload = _build_valid_payload(
                task=t,
                annotator=annotator,
                true_cond=true_cond,
                timestamp=sub_ts,
                is_correct=is_correct,
                mean_duration=mean_time,
                speed_sigma=sigma,
                rng=rng,
                is_rework=is_rework,
                is_escalated=is_escalated,
            )
            clean_records.append(clean_payload)
            day_events_done += 1

            # Write a sample of raw JSON payloads to data/raw/
            if raw_sample_written < num_raw_samples and rng.random() < 0.15:
                ts_str = sub_ts.strftime("%Y%m%dT%H%M%S")
                raw_filename = f"{t['task_id']}_{annotator['id']}_{ts_str}.json"
                with open(RAW_DIR / raw_filename, "w", encoding="utf-8") as f:
                    json.dump(clean_payload, f, indent=2)
                raw_sample_written += 1

        # Generate controlled rejection events for this day
        num_rejections_today = int(round(target_today * rejection_prob))
        for _ in range(num_rejections_today):
            rej_task = rng.choice(tasks)
            rej_annotator = rng.choice(ANNOTATOR_ROSTER)
            rej_ts = day_date + timedelta(seconds=rng.randint(0, 10 * 3600))

            rej_type = rng.choice([
                "ERR_CONDITIONAL_FIELD_MISSING",
                "ERR_UNEXPECTED_FIELD_PRESENT",
                "ERR_DESCRIPTION_TOO_SHORT",
                "ERR_INVALID_LABEL",
                "ERR_IMPOSSIBLE_TIME",
                "ERR_DUPLICATE_SUBMISSION",
            ])

            if rej_type == "ERR_CONDITIONAL_FIELD_MISSING":
                code = RejectionCode.ERR_CONDITIONAL_FIELD_MISSING.value
                reason = "Condition OPEN_BOX requires packaging_condition and seal_condition."
                stage = "STAGE_3_CONDITIONAL_RULES"
            elif rej_type == "ERR_UNEXPECTED_FIELD_PRESENT":
                code = RejectionCode.ERR_UNEXPECTED_FIELD_PRESENT.value
                reason = "Condition NEW strictly forbids damage_type or packaging fields."
                stage = "STAGE_3_CONDITIONAL_RULES"
            elif rej_type == "ERR_DESCRIPTION_TOO_SHORT":
                code = RejectionCode.ERR_DESCRIPTION_TOO_SHORT.value
                reason = "Damage description must be at least 10 characters long, got 5."
                stage = "STAGE_3_CONDITIONAL_RULES"
            elif rej_type == "ERR_INVALID_LABEL":
                code = RejectionCode.ERR_INVALID_LABEL.value
                reason = "Primary condition 'REFURBISHED_GRADE_B' is invalid."
                stage = "STAGE_2_CATEGORICAL"
            elif rej_type == "ERR_IMPOSSIBLE_TIME":
                code = RejectionCode.ERR_IMPOSSIBLE_TIME.value
                reason = "Processing time 0.12s is outside physically possible bounds [0.5s, 1800.0s]."
                stage = "STAGE_4_OPERATIONAL"
            else:
                code = RejectionCode.ERR_DUPLICATE_SUBMISSION.value
                reason = f"Duplicate submission detected for task_id '{rej_task['task_id']}' by annotator '{rej_annotator['id']}'."
                stage = "STAGE_1_SCHEMA"

            rejected_records.append({
                "task_id": rej_task["task_id"],
                "annotator_id": rej_annotator["id"],
                "rejection_code": code,
                "rejection_reason": reason,
                "validation_stage": stage,
                "raw_payload": {
                    "task_id": rej_task["task_id"],
                    "annotator_id": rej_annotator["id"],
                    "condition": "NEW",
                    "damage_type": "CRUSHED_BOX" if code == RejectionCode.ERR_UNEXPECTED_FIELD_PRESENT.value else None,
                },
                "timestamp": rej_ts.isoformat(),
            })

    # Sort clean records chronologically
    clean_records.sort(key=lambda r: r["annotation_timestamp"])
    rejected_records.sort(key=lambda r: r["timestamp"])

    # Stream to JSONL files
    print(f"[Simulation] Writing {len(clean_records):,} validated records -> {processed_file}...")
    with open(processed_file, "w", encoding="utf-8") as f:
        for r in clean_records:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")

    print(f"[Simulation] Writing {len(rejected_records):,} rejected audit records -> {rejected_file}...")
    with open(rejected_file, "w", encoding="utf-8") as f:
        for r in rejected_records:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")

    print(f"[Simulation] Wrote {raw_sample_written} sample raw JSON files into {raw_dir} for workstation testing.")

    return {
        "clean_count": len(clean_records),
        "rejected_count": len(rejected_records),
        "raw_samples": raw_sample_written,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate Enterprise Human Annotation Operations")
    parser.add_argument("--count", type=int, default=25000, help="Target clean annotations")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Deterministic random seed")
    parser.add_argument("--raw-samples", type=int, default=60, help="Raw JSON sample files to generate")
    args = parser.parse_args()

    results = simulate_enterprise_operations(
        target_clean=args.count,
        seed=args.seed,
        num_raw_samples=args.raw_samples,
    )
    print(f"[Done] Clean: {results['clean_count']:,} | Rejected: {results['rejected_count']:,}")
