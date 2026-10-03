"""
Unit tests for Specification Validator (pipeline/validate_spec.py).
Verifies that valid specifications are accepted and that all malformed,
inconsistent, or conflicting specification structures are caught.
"""

import copy
import pytest
import yaml

from pipeline.validate_spec import (
    validate_specification_dict,
    validate_specification_file,
)


@pytest.fixture
def valid_spec_dict():
    """Load the primary specification file as a reference valid dictionary."""
    with open("schemas/annotation.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_production_spec_file_is_valid():
    """Ensure the actual repository schemas/annotation.yaml passes validation."""
    is_valid, errors = validate_specification_file("schemas/annotation.yaml")
    assert is_valid is True, f"Production spec failed validation: {errors}"
    assert len(errors) == 0


def test_missing_top_level_keys(valid_spec_dict):
    """Missing any required root key must trigger validation errors."""
    for key in ["task", "labels", "fields", "conditional_rules", "metadata_fields"]:
        spec = copy.deepcopy(valid_spec_dict)
        del spec[key]
        errors = validate_specification_dict(spec)
        assert any(f"Missing required top-level key: '{key}'" in err for err in errors)


def test_duplicate_labels_rejected(valid_spec_dict):
    """Duplicate primary condition labels must be rejected."""
    spec = copy.deepcopy(valid_spec_dict)
    spec["labels"] = ["NEW", "OPEN_BOX", "NEW"]
    errors = validate_specification_dict(spec)
    assert any("Duplicate primary label detected: 'NEW'" in err for err in errors)


def test_unsupported_field_type_rejected(valid_spec_dict):
    """Unsupported data types in fields must be rejected."""
    spec = copy.deepcopy(valid_spec_dict)
    spec["fields"]["packaging_condition"]["type"] = "unsupported_blob"
    errors = validate_specification_dict(spec)
    assert any("unsupported type 'unsupported_blob'" in err for err in errors)


def test_enum_without_allowed_values_rejected(valid_spec_dict):
    """Enum fields without allowed_values must be rejected."""
    spec = copy.deepcopy(valid_spec_dict)
    spec["fields"]["packaging_condition"]["allowed_values"] = []
    errors = validate_specification_dict(spec)
    assert any("must define a non-empty 'allowed_values' list" in err for err in errors)


def test_duplicate_enum_allowed_values_rejected(valid_spec_dict):
    """Duplicate values inside an enum must be rejected."""
    spec = copy.deepcopy(valid_spec_dict)
    spec["fields"]["packaging_condition"]["allowed_values"] = ["INTACT", "WORN", "INTACT"]
    errors = validate_specification_dict(spec)
    assert any("contains duplicate values in 'allowed_values'" in err for err in errors)


def test_invalid_default_value_rejected(valid_spec_dict):
    """Default values not present in allowed_values must be rejected."""
    spec = copy.deepcopy(valid_spec_dict)
    spec["fields"]["packaging_condition"]["default"] = "NON_EXISTENT_STATE"
    errors = validate_specification_dict(spec)
    assert any("is not in allowed_values" in err for err in errors)


def test_broken_reference_in_conditional_rules(valid_spec_dict):
    """Conditional rules referencing non-existent fields must be rejected."""
    spec = copy.deepcopy(valid_spec_dict)
    spec["conditional_rules"]["DAMAGED"]["required_fields"].append("phantom_field")
    errors = validate_specification_dict(spec)
    assert any("requires undeclared field 'phantom_field'" in err for err in errors)


def test_conflict_required_and_forbidden_fields(valid_spec_dict):
    """A field cannot be both required and forbidden in the same condition branch."""
    spec = copy.deepcopy(valid_spec_dict)
    spec["conditional_rules"]["OPEN_BOX"]["forbidden_fields"].append("packaging_condition")
    errors = validate_specification_dict(spec)
    assert any("cannot be both required and forbidden" in err for err in errors)


def test_missing_conditional_branch_for_label(valid_spec_dict):
    """Every declared label must have a corresponding conditional rule branch."""
    spec = copy.deepcopy(valid_spec_dict)
    del spec["conditional_rules"]["DAMAGED"]
    errors = validate_specification_dict(spec)
    assert any("Missing conditional rule branch for declared label: 'DAMAGED'" in err for err in errors)


def test_nonexistent_file_handling():
    """Validating a non-existent file returns False and meaningful error."""
    is_valid, errors = validate_specification_file("schemas/non_existent_file.yaml")
    assert is_valid is False
    assert any("not found" in err for err in errors)
