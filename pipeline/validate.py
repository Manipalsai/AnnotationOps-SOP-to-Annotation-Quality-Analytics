"""
Multi-Stage Ingestion and Validation Engine for AnnotationOps.

Executes a 4-tier validation pipeline:
- Stage 1: Structural Schema & Essential Identifiers (task_id, annotator_id, timestamp)
- Stage 2: Categorical Integrity & Controlled Vocabulary
- Stage 3: SOP Conditional Business Logic
- Stage 4: Operational Data Integrity & Anomaly Screening (pacing, duplicates)

Routes clean records to 'data/processed/clean_annotations.jsonl' and
invalid records to 'data/rejected/rejected_annotations.jsonl' with standardized rejection codes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
PROCESSED_FILE = DATA_DIR / "processed" / "clean_annotations.jsonl"
REJECTED_FILE = DATA_DIR / "rejected" / "rejected_annotations.jsonl"

# Operational Thresholds (mirrors schemas/annotation.yaml)
MIN_VALID_TIME_SECONDS = 0.5
MAX_VALID_TIME_SECONDS = 1800.0
FAST_PACING_ANOMALY_SECONDS = 2.0


class ValidationResult:
    """Encapsulates the outcome of validating a single raw submission."""

    def __init__(
        self,
        is_valid: bool,
        record: AnnotationRecord | None = None,
        rejected: RejectedRecord | None = None,
        anomaly_flag: str | None = None,
    ) -> None:
        self.is_valid = is_valid
        self.record = record
        self.rejected = rejected
        self.anomaly_flag = anomaly_flag


def validate_raw_payload(payload: dict[str, Any], seen_submissions: set[tuple[str, str]] | None = None) -> ValidationResult:
    """
    Validate a raw dictionary submission against all operational and scientific gates.
    seen_submissions: optional set of (task_id, annotator_id) tuples to detect duplicates.
    """
    task_id = payload.get("task_id")
    annotator_id = payload.get("annotator_id")

    # -------------------------------------------------------------
    # STAGE 1: Structural Schema & Identifier Verification
    # -------------------------------------------------------------
    if not task_id or not str(task_id).strip():
        return ValidationResult(
            is_valid=False,
            rejected=RejectedRecord(
                task_id=None,
                annotator_id=str(annotator_id) if annotator_id else None,
                rejection_code=RejectionCode.ERR_MISSING_TASK_ID.value,
                rejection_reason="Submission is missing a mandatory non-empty task_id.",
                validation_stage="STAGE_1_SCHEMA",
                raw_payload=payload,
            ),
        )

    if not annotator_id or not str(annotator_id).strip():
        return ValidationResult(
            is_valid=False,
            rejected=RejectedRecord(
                task_id=str(task_id),
                annotator_id=None,
                rejection_code=RejectionCode.ERR_MISSING_ANNOTATOR_ID.value,
                rejection_reason="Submission is missing a mandatory non-empty annotator_id.",
                validation_stage="STAGE_1_SCHEMA",
                raw_payload=payload,
            ),
        )

    # Duplicate submission check within run
    sub_key = (str(task_id).strip(), str(annotator_id).strip())
    if seen_submissions is not None and sub_key in seen_submissions:
        return ValidationResult(
            is_valid=False,
            rejected=RejectedRecord(
                task_id=str(task_id),
                annotator_id=str(annotator_id),
                rejection_code=RejectionCode.ERR_DUPLICATE_SUBMISSION.value,
                rejection_reason=f"Duplicate submission detected for task_id '{task_id}' by annotator '{annotator_id}'.",
                validation_stage="STAGE_1_SCHEMA",
                raw_payload=payload,
            ),
        )

    # -------------------------------------------------------------
    # STAGE 2: Categorical Integrity
    # -------------------------------------------------------------
    condition_val = payload.get("condition")
    if condition_val not in [c.value for c in PrimaryCondition]:
        return ValidationResult(
            is_valid=False,
            rejected=RejectedRecord(
                task_id=str(task_id),
                annotator_id=str(annotator_id),
                rejection_code=RejectionCode.ERR_INVALID_LABEL.value,
                rejection_reason=f"Primary condition '{condition_val}' is invalid. Allowed: {[c.value for c in PrimaryCondition]}",
                validation_stage="STAGE_2_CATEGORICAL",
                raw_payload=payload,
            ),
        )

    # -------------------------------------------------------------
    # STAGE 3: SOP Conditional Business Logic (Pydantic Model)
    # -------------------------------------------------------------
    try:
        validated_record = AnnotationRecord(**payload)
    except Exception as exc:
        err_msg = str(exc)
        # Classify specific conditional violation code
        if "Condition NEW strictly forbids" in err_msg or "forbids" in err_msg:
            code = RejectionCode.ERR_UNEXPECTED_FIELD_PRESENT.value
        elif "requires fields" in err_msg:
            code = RejectionCode.ERR_CONDITIONAL_FIELD_MISSING.value
        elif "at least 10 characters long" in err_msg:
            code = RejectionCode.ERR_DESCRIPTION_TOO_SHORT.value
        elif "Input should be" in err_msg:
            code = RejectionCode.ERR_INVALID_ENUM_VALUE.value
        else:
            code = RejectionCode.ERR_SCHEMA_MISMATCH.value

        return ValidationResult(
            is_valid=False,
            rejected=RejectedRecord(
                task_id=str(task_id),
                annotator_id=str(annotator_id),
                rejection_code=code,
                rejection_reason=err_msg,
                validation_stage="STAGE_3_CONDITIONAL_RULES",
                raw_payload=payload,
            ),
        )

    # -------------------------------------------------------------
    # STAGE 4: Operational Integrity & Anomaly Screening
    # -------------------------------------------------------------
    proc_time = validated_record.processing_time_seconds
    if proc_time < MIN_VALID_TIME_SECONDS or proc_time > MAX_VALID_TIME_SECONDS:
        return ValidationResult(
            is_valid=False,
            rejected=RejectedRecord(
                task_id=str(task_id),
                annotator_id=str(annotator_id),
                rejection_code=RejectionCode.ERR_IMPOSSIBLE_TIME.value,
                rejection_reason=f"Processing time {proc_time}s is outside physically possible bounds [{MIN_VALID_TIME_SECONDS}s, {MAX_VALID_TIME_SECONDS}s].",
                validation_stage="STAGE_4_OPERATIONAL",
                raw_payload=payload,
            ),
        )

    # Fast pacing check: Record is valid, but flagged for quality review
    anomaly_flag = None
    if proc_time < FAST_PACING_ANOMALY_SECONDS:
        anomaly_flag = RejectionCode.WARN_SPEED_ANOMALY_FAST.value

    return ValidationResult(
        is_valid=True,
        record=validated_record,
        rejected=None,
        anomaly_flag=anomaly_flag,
    )


def process_raw_directory(
    raw_dir: str | Path = DATA_DIR / "raw",
    processed_out: str | Path = PROCESSED_FILE,
    rejected_out: str | Path = REJECTED_FILE,
) -> tuple[int, int, int]:
    """
    Scan data/raw/ directory for new raw submission files, validate each record,
    and append to processed and rejected sinks idempotently.

    Returns (total_scanned, valid_count, rejected_count).
    """
    raw_path = Path(raw_dir)
    proc_path = Path(processed_out)
    rej_path = Path(rejected_out)

    proc_path.parent.mkdir(parents=True, exist_ok=True)
    rej_path.parent.mkdir(parents=True, exist_ok=True)

    raw_files = sorted(list(raw_path.glob("*.json")))
    # Ingestion ledger tracks previously processed raw files for true idempotency
    ledger_file = proc_path.parent / ".ingested_files.json"
    ingested_files: dict[str, str] = {}
    if ledger_file.exists():
        try:
            with open(ledger_file, "r", encoding="utf-8") as f:
                ingested_files = json.load(f)
        except Exception:
            ingested_files = {}

    seen_submissions: set[tuple[str, str]] = set()
    if proc_path.exists():
        with open(proc_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    seen_submissions.add((str(item.get("task_id", "")), str(item.get("annotator_id", ""))))

    valid_records: list[dict[str, Any]] = []
    rejected_records: list[dict[str, Any]] = []

    for f_path in raw_files:
        # If this exact file was already processed in a prior run, skip (idempotency)
        if f_path.name in ingested_files:
            continue

        try:
            with open(f_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as exc:
            rejected_records.append(
                RejectedRecord(
                    task_id=None,
                    annotator_id=None,
                    rejection_code=RejectionCode.ERR_SCHEMA_MISMATCH.value,
                    rejection_reason=f"Corrupt JSON file {f_path.name}: {exc}",
                    validation_stage="STAGE_1_SCHEMA",
                    raw_payload={"filename": f_path.name},
                ).model_dump(mode="json")
            )
            ingested_files[f_path.name] = "CORRUPT"
            continue

        result = validate_raw_payload(payload, seen_submissions=seen_submissions)

        if result.is_valid and result.record:
            rec_dict = result.record.model_dump(mode="json")
            rec_dict["anomaly_flag"] = result.anomaly_flag
            valid_records.append(rec_dict)
            seen_submissions.add((result.record.task_id, result.record.annotator_id))
            ingested_files[f_path.name] = "VALID"
        elif result.rejected:
            rejected_records.append(result.rejected.model_dump(mode="json"))
            ingested_files[f_path.name] = "REJECTED"

    # Write clean records
    if valid_records:
        with open(proc_path, "a", encoding="utf-8") as f:
            for v_rec in valid_records:
                f.write(json.dumps(v_rec) + "\n")

    # Write rejected records
    if rejected_records:
        with open(rej_path, "a", encoding="utf-8") as f:
            for r_rec in rejected_records:
                f.write(json.dumps(r_rec) + "\n")

    # Persist updated ingestion ledger
    with open(ledger_file, "w", encoding="utf-8") as f:
        json.dump(ingested_files, f, indent=2)

    return len(raw_files), len(valid_records), len(rejected_records)
