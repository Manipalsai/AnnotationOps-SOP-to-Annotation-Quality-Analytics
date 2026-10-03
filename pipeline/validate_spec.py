"""
Specification Validator Module
Validates the structural and logical integrity of the YAML annotation specification.

Enforces:
- Presence of required top-level keys ('task', 'labels', 'fields', 'conditional_rules', 'metadata_fields')
- Validity of primary condition labels (no duplicates, non-empty)
- Consistency of declared fields (valid types, allowed enum values, non-empty)
- Validity of conditional rules (branches match declared labels, all referenced fields exist in 'fields')
- Mutually exclusive conflict checks (a field cannot be both required and forbidden in the same condition)
- Valid metadata field definitions
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
import yaml

SUPPORTED_FIELD_TYPES = {"string", "enum", "integer", "float", "boolean", "datetime"}


class SpecValidationError(Exception):
    """Raised when an annotation specification contract fails validation."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"Specification failed validation with {len(errors)} error(s):\n - " + "\n - ".join(errors))


def validate_specification_dict(spec: Any) -> list[str]:
    """
    Validate a parsed specification dictionary against structural and business constraints.
    Returns a list of error strings. Empty list indicates full compliance.
    """
    errors: list[str] = []

    if not isinstance(spec, dict):
        return ["Specification root must be a YAML mapping (dictionary)."]

    # 1. Top-level required keys
    required_top_keys = ["task", "labels", "fields", "conditional_rules", "metadata_fields"]
    for key in required_top_keys:
        if key not in spec:
            errors.append(f"Missing required top-level key: '{key}'")

    if errors:
        return errors  # Cannot safely inspect nested structures without core keys

    # 2. Validate 'task' section
    task = spec.get("task")
    if not isinstance(task, dict):
        errors.append("'task' must be a dictionary.")
    else:
        for req_prop in ["name", "version", "description"]:
            if req_prop not in task or not str(task.get(req_prop, "")).strip():
                errors.append(f"Task definition missing or empty property: '{req_prop}'")

    # 3. Validate 'labels'
    labels = spec.get("labels")
    if not isinstance(labels, list) or len(labels) == 0:
        errors.append("'labels' must be a non-empty list of primary condition names.")
        declared_labels: set[str] = set()
    else:
        declared_labels = set()
        for idx, lbl in enumerate(labels):
            if not isinstance(lbl, str) or not lbl.strip():
                errors.append(f"Label at index {idx} must be a non-empty string.")
            elif lbl in declared_labels:
                errors.append(f"Duplicate primary label detected: '{lbl}'")
            else:
                declared_labels.add(lbl)

    # 4. Validate 'fields'
    fields = spec.get("fields")
    if not isinstance(fields, dict) or len(fields) == 0:
        errors.append("'fields' must be a dictionary of field definitions.")
        declared_field_names: set[str] = set()
    else:
        declared_field_names = set(fields.keys())
        for f_name, f_def in fields.items():
            if not isinstance(f_def, dict):
                errors.append(f"Field '{f_name}' definition must be a dictionary.")
                continue

            # Field type check
            f_type = f_def.get("type")
            if f_type not in SUPPORTED_FIELD_TYPES:
                errors.append(
                    f"Field '{f_name}' has unsupported type '{f_type}'. "
                    f"Supported types: {sorted(list(SUPPORTED_FIELD_TYPES))}"
                )

            # Enum values check
            if f_type == "enum":
                allowed = f_def.get("allowed_values")
                if not isinstance(allowed, list) or len(allowed) == 0:
                    errors.append(f"Enum field '{f_name}' must define a non-empty 'allowed_values' list.")
                elif len(allowed) != len(set(allowed)):
                    errors.append(f"Enum field '{f_name}' contains duplicate values in 'allowed_values'.")

            # Default value validation
            if "default" in f_def and f_def["default"] is not None:
                default_val = f_def["default"]
                if f_type == "enum" and default_val not in f_def.get("allowed_values", []):
                    errors.append(f"Default value '{default_val}' for field '{f_name}' is not in allowed_values.")

    # 5. Validate 'conditional_rules'
    rules = spec.get("conditional_rules")
    if not isinstance(rules, dict):
        errors.append("'conditional_rules' must be a dictionary keyed by primary condition labels.")
    else:
        # Check rule labels match declared labels
        for cond_label, branch in rules.items():
            if cond_label not in declared_labels:
                errors.append(
                    f"Conditional branch '{cond_label}' is not defined in declared labels: {sorted(list(declared_labels))}"
                )

            if not isinstance(branch, dict):
                errors.append(f"Conditional branch '{cond_label}' must be a dictionary.")
                continue

            req = branch.get("required_fields", [])
            forb = branch.get("forbidden_fields", [])

            if not isinstance(req, list):
                errors.append(f"'required_fields' for '{cond_label}' must be a list.")
                req = []
            if not isinstance(forb, list):
                errors.append(f"'forbidden_fields' for '{cond_label}' must be a list.")
                forb = []

            # Check for broken references to non-existent fields
            for r_f in req:
                if r_f not in declared_field_names:
                    errors.append(f"Broken reference: '{cond_label}' requires undeclared field '{r_f}'.")
            for f_f in forb:
                if f_f not in declared_field_names:
                    errors.append(f"Broken reference: '{cond_label}' forbids undeclared field '{f_f}'.")

            # Check mutual exclusion between required and forbidden
            overlap = set(req).intersection(set(forb))
            if overlap:
                errors.append(
                    f"Conflict in '{cond_label}': Fields cannot be both required and forbidden: {sorted(list(overlap))}"
                )

        # Ensure all declared labels have a conditional rule branch
        for lbl in declared_labels:
            if lbl not in rules:
                errors.append(f"Missing conditional rule branch for declared label: '{lbl}'")

    # 6. Validate 'metadata_fields'
    meta = spec.get("metadata_fields")
    if not isinstance(meta, dict):
        errors.append("'metadata_fields' must be a dictionary.")
    else:
        for m_name, m_def in meta.items():
            if not isinstance(m_def, dict):
                errors.append(f"Metadata field '{m_name}' must be a dictionary.")
                continue
            m_type = m_def.get("type")
            if m_type not in SUPPORTED_FIELD_TYPES:
                errors.append(
                    f"Metadata field '{m_name}' has unsupported type '{m_type}'."
                )

    return errors


def validate_specification_file(file_path: str | Path) -> tuple[bool, list[str]]:
    """
    Load and validate a YAML specification file.
    Returns (is_valid, error_list).
    """
    path = Path(file_path)
    if not path.exists():
        return False, [f"Specification file not found at: {path}"]

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        return False, [f"YAML parsing error in {path.name}: {exc}"]
    except Exception as exc:
        return False, [f"Error reading file {path.name}: {exc}"]

    errors = validate_specification_dict(content)
    return (len(errors) == 0, errors)


if __name__ == "__main__":
    spec_path = sys.argv[1] if len(sys.argv) > 1 else "schemas/annotation.yaml"
    is_valid, errs = validate_specification_file(spec_path)
    if is_valid:
        print(f"SUCCESS: Specification '{spec_path}' is structurally valid and fully compliant.")
        sys.exit(0)
    else:
        print(f"FAILED: Specification '{spec_path}' has {len(errs)} error(s):")
        for err in errs:
            print(f"  - {err}")
        sys.exit(1)
