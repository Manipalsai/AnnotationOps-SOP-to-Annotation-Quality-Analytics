"""
Pydantic Data Models and Domain Enums for AnnotationOps.
Strictly mirrors the schema contract defined in schemas/annotation.yaml and SOP-OPS-2026-001.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PrimaryCondition(str, Enum):
    NEW = "NEW"
    OPEN_BOX = "OPEN_BOX"
    DAMAGED = "DAMAGED"


class PackagingCondition(str, Enum):
    INTACT = "INTACT"
    WORN = "WORN"
    MISSING = "MISSING"


class SealCondition(str, Enum):
    BROKEN = "BROKEN"
    MISSING = "MISSING"
    RESEALED = "RESEALED"


class DamageType(str, Enum):
    CRUSHED_BOX = "CRUSHED_BOX"
    TEAR_PUNCTURE = "TEAR_PUNCTURE"
    LIQUID_STAIN = "LIQUID_STAIN"
    ITEM_DEFECT = "ITEM_DEFECT"


class DamageSeverity(str, Enum):
    MINOR = "MINOR"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"


class RejectionCode(str, Enum):
    ERR_MISSING_TASK_ID = "ERR_MISSING_TASK_ID"
    ERR_MISSING_ANNOTATOR_ID = "ERR_MISSING_ANNOTATOR_ID"
    ERR_INVALID_LABEL = "ERR_INVALID_LABEL"
    ERR_CONDITIONAL_FIELD_MISSING = "ERR_CONDITIONAL_FIELD_MISSING"
    ERR_UNEXPECTED_FIELD_PRESENT = "ERR_UNEXPECTED_FIELD_PRESENT"
    ERR_INVALID_ENUM_VALUE = "ERR_INVALID_ENUM_VALUE"
    ERR_DESCRIPTION_TOO_SHORT = "ERR_DESCRIPTION_TOO_SHORT"
    ERR_IMPOSSIBLE_TIME = "ERR_IMPOSSIBLE_TIME"
    ERR_DUPLICATE_SUBMISSION = "ERR_DUPLICATE_SUBMISSION"
    ERR_SCHEMA_MISMATCH = "ERR_SCHEMA_MISMATCH"
    WARN_SPEED_ANOMALY_FAST = "WARN_SPEED_ANOMALY_FAST"
    WARN_SPEED_ANOMALY_SLOW = "WARN_SPEED_ANOMALY_SLOW"


class AnnotationRecord(BaseModel):
    """
    Standard verified annotation record.
    Enforces conditional logic directly matching SOP-OPS-2026-001.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    task_id: str = Field(..., min_length=1, description="Unique ID for task")
    image_id: str = Field(..., min_length=1, description="Image reference identifier")
    annotator_id: str = Field(..., min_length=1, description="Annotator identifier")
    condition: PrimaryCondition = Field(..., description="Primary condition classification")

    # Secondary conditional fields
    packaging_condition: PackagingCondition | None = Field(default=None)
    seal_condition: SealCondition | None = Field(default=None)
    damage_type: DamageType | None = Field(default=None)
    damage_severity: DamageSeverity | None = Field(default=None)
    description: str | None = Field(default=None, max_length=250)

    # Operational audit metadata
    annotation_timestamp: datetime = Field(..., description="UTC timestamp of submission")
    processing_time_seconds: float = Field(..., ge=0.01, le=1800.0, description="Duration in seconds")
    schema_version: str = Field(default="1.0.0", description="Specification schema version")

    @field_validator("description")
    @classmethod
    def validate_description_length(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) < 10:
            raise ValueError(f"Damage description must be at least 10 characters long, got {len(v.strip())}.")
        return v.strip() if v else None

    @model_validator(mode="after")
    def validate_conditional_rules(self) -> AnnotationRecord:
        cond = self.condition

        if cond == PrimaryCondition.NEW:
            # All secondary fields must be null
            forbidden = []
            if self.packaging_condition is not None:
                forbidden.append("packaging_condition")
            if self.seal_condition is not None:
                forbidden.append("seal_condition")
            if self.damage_type is not None:
                forbidden.append("damage_type")
            if self.damage_severity is not None:
                forbidden.append("damage_severity")
            if self.description is not None:
                forbidden.append("description")

            if forbidden:
                raise ValueError(
                    f"Condition NEW strictly forbids secondary fields: {', '.join(forbidden)}"
                )

        elif cond == PrimaryCondition.OPEN_BOX:
            # packaging_condition & seal_condition required; damage fields forbidden
            missing = []
            if self.packaging_condition is None:
                missing.append("packaging_condition")
            if self.seal_condition is None:
                missing.append("seal_condition")
            if missing:
                raise ValueError(
                    f"Condition OPEN_BOX requires fields: {', '.join(missing)}"
                )

            forbidden = []
            if self.damage_type is not None:
                forbidden.append("damage_type")
            if self.damage_severity is not None:
                forbidden.append("damage_severity")
            if self.description is not None:
                forbidden.append("description")
            if forbidden:
                raise ValueError(
                    f"Condition OPEN_BOX forbids damage fields: {', '.join(forbidden)}"
                )

        elif cond == PrimaryCondition.DAMAGED:
            # damage_type, damage_severity, description required; open box fields forbidden
            missing = []
            if self.damage_type is None:
                missing.append("damage_type")
            if self.damage_severity is None:
                missing.append("damage_severity")
            if self.description is None:
                missing.append("description")
            if missing:
                raise ValueError(
                    f"Condition DAMAGED requires fields: {', '.join(missing)}"
                )

            forbidden = []
            if self.packaging_condition is not None:
                forbidden.append("packaging_condition")
            if self.seal_condition is not None:
                forbidden.append("seal_condition")
            if forbidden:
                raise ValueError(
                    f"Condition DAMAGED forbids packaging/seal fields: {', '.join(forbidden)}"
                )

        return self


class RejectedRecord(BaseModel):
    """Audit log entry capturing any rejected submission and root cause."""
    task_id: str | None = None
    annotator_id: str | None = None
    rejection_code: str
    rejection_reason: str
    validation_stage: str
    raw_payload: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class GoldRecord(BaseModel):
    """Ground truth benchmark record used for quality scoring."""
    task_id: str
    image_id: str
    ground_truth_condition: PrimaryCondition
    ground_truth_packaging_condition: PackagingCondition | None = None
    ground_truth_seal_condition: SealCondition | None = None
    ground_truth_damage_type: DamageType | None = None
    ground_truth_damage_severity: DamageSeverity | None = None
    ground_truth_description: str | None = None
    difficulty: str = "MEDIUM"  # EASY, MEDIUM, HARD
    verified_by: str = "Lead Quality Specialist"
    synthetic: bool = True
