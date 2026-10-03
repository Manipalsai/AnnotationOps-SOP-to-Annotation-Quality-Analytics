"""
Unit tests for Domain Models and Conditional Validation (schemas/models.py).
Verifies that:
- Valid NEW, OPEN_BOX, and DAMAGED records pass schema validation.
- Forbidden or missing conditional fields raise descriptive validation errors.
- Descriptions meet minimum length thresholds.
- Processing times are validated within physical operating limits.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from schemas.models import (
    AnnotationRecord,
    PrimaryCondition,
    PackagingCondition,
    SealCondition,
    DamageType,
    DamageSeverity,
)


def get_base_payload():
    return {
        "task_id": "TSK-00101",
        "image_id": "IMG-00101.jpg",
        "annotator_id": "ANNO-04",
        "annotation_timestamp": datetime.now(timezone.utc),
        "processing_time_seconds": 14.5,
        "schema_version": "1.0.0",
    }


def test_valid_new_record():
    """Condition NEW without secondary fields is valid."""
    payload = get_base_payload()
    payload["condition"] = PrimaryCondition.NEW
    record = AnnotationRecord(**payload)
    assert record.condition == PrimaryCondition.NEW
    assert record.packaging_condition is None
    assert record.damage_type is None


def test_invalid_new_record_with_forbidden_fields():
    """Condition NEW fails if packaging or damage fields are populated."""
    payload = get_base_payload()
    payload["condition"] = PrimaryCondition.NEW
    payload["packaging_condition"] = PackagingCondition.INTACT

    with pytest.raises(ValidationError) as exc:
        AnnotationRecord(**payload)
    assert "Condition NEW strictly forbids secondary fields: packaging_condition" in str(exc.value)


def test_valid_open_box_record():
    """Condition OPEN_BOX requires packaging_condition and seal_condition."""
    payload = get_base_payload()
    payload["condition"] = PrimaryCondition.OPEN_BOX
    payload["packaging_condition"] = PackagingCondition.INTACT
    payload["seal_condition"] = SealCondition.BROKEN

    record = AnnotationRecord(**payload)
    assert record.condition == PrimaryCondition.OPEN_BOX
    assert record.packaging_condition == PackagingCondition.INTACT
    assert record.seal_condition == SealCondition.BROKEN


def test_invalid_open_box_missing_seal_condition():
    """Condition OPEN_BOX fails if seal_condition is missing."""
    payload = get_base_payload()
    payload["condition"] = PrimaryCondition.OPEN_BOX
    payload["packaging_condition"] = PackagingCondition.INTACT

    with pytest.raises(ValidationError) as exc:
        AnnotationRecord(**payload)
    assert "Condition OPEN_BOX requires fields: seal_condition" in str(exc.value)


def test_invalid_open_box_with_damage_fields():
    """Condition OPEN_BOX fails if damage fields are attached."""
    payload = get_base_payload()
    payload["condition"] = PrimaryCondition.OPEN_BOX
    payload["packaging_condition"] = PackagingCondition.INTACT
    payload["seal_condition"] = SealCondition.BROKEN
    payload["damage_type"] = DamageType.CRUSHED_BOX

    with pytest.raises(ValidationError) as exc:
        AnnotationRecord(**payload)
    assert "Condition OPEN_BOX forbids damage fields: damage_type" in str(exc.value)


def test_valid_damaged_record():
    """Condition DAMAGED requires damage_type, damage_severity, and description."""
    payload = get_base_payload()
    payload["condition"] = PrimaryCondition.DAMAGED
    payload["damage_type"] = DamageType.CRUSHED_BOX
    payload["damage_severity"] = DamageSeverity.MODERATE
    payload["description"] = "Front left carton edge crushed inward 4cm."

    record = AnnotationRecord(**payload)
    assert record.condition == PrimaryCondition.DAMAGED
    assert record.damage_type == DamageType.CRUSHED_BOX
    assert record.damage_severity == DamageSeverity.MODERATE


def test_invalid_damaged_missing_severity():
    """Condition DAMAGED fails if damage_severity is missing."""
    payload = get_base_payload()
    payload["condition"] = PrimaryCondition.DAMAGED
    payload["damage_type"] = DamageType.TEAR_PUNCTURE
    payload["description"] = "Side panel tear measuring 25mm."

    with pytest.raises(ValidationError) as exc:
        AnnotationRecord(**payload)
    assert "Condition DAMAGED requires fields: damage_severity" in str(exc.value)


def test_invalid_damaged_description_too_short():
    """Damage descriptions under 10 characters are rejected."""
    payload = get_base_payload()
    payload["condition"] = PrimaryCondition.DAMAGED
    payload["damage_type"] = DamageType.TEAR_PUNCTURE
    payload["damage_severity"] = DamageSeverity.MINOR
    payload["description"] = "Broken"  # 6 chars

    with pytest.raises(ValidationError) as exc:
        AnnotationRecord(**payload)
    assert "Damage description must be at least 10 characters long" in str(exc.value)


def test_invalid_damaged_with_packaging_condition():
    """Condition DAMAGED fails if packaging_condition is attached."""
    payload = get_base_payload()
    payload["condition"] = PrimaryCondition.DAMAGED
    payload["damage_type"] = DamageType.LIQUID_STAIN
    payload["damage_severity"] = DamageSeverity.SEVERE
    payload["description"] = "Liquid saturation throughout primary package."
    payload["packaging_condition"] = PackagingCondition.WORN

    with pytest.raises(ValidationError) as exc:
        AnnotationRecord(**payload)
    assert "Condition DAMAGED forbids packaging/seal fields: packaging_condition" in str(exc.value)


def test_processing_time_bounds():
    """Processing times must be positive and non-zero."""
    payload = get_base_payload()
    payload["condition"] = PrimaryCondition.NEW
    payload["processing_time_seconds"] = 0.0

    with pytest.raises(ValidationError):
        AnnotationRecord(**payload)
