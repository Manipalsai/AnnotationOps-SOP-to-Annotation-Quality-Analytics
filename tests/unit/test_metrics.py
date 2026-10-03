"""
Unit tests for Quality Science and Metrics Engine (pipeline/metrics.py).
Verifies statistical calculations:
- Cohen's Kappa under perfect agreement, chance, and disagreement
- Confusion matrix precision/recall computations
- Mathematical properties and edge cases
"""

import pytest
from pipeline.metrics import (
    calculate_cohens_kappa,
    direct_cohens_kappa,
    calculate_confusion_matrix_data,
)


def test_cohens_kappa_perfect_agreement():
    """Identical rater labels must yield Cohen's Kappa = 1.0."""
    y_true = ["NEW", "OPEN_BOX", "DAMAGED", "NEW", "OPEN_BOX"]
    y_pred = ["NEW", "OPEN_BOX", "DAMAGED", "NEW", "OPEN_BOX"]

    kappa = calculate_cohens_kappa(y_true, y_pred)
    assert kappa == 1.0


def test_cohens_kappa_single_class_agreement():
    """All items belonging to one class and all matched must yield 1.0."""
    y_true = ["NEW", "NEW", "NEW"]
    y_pred = ["NEW", "NEW", "NEW"]

    kappa = calculate_cohens_kappa(y_true, y_pred)
    assert kappa == 1.0


def test_cohens_kappa_near_chance():
    """Random / balanced misclassification yields kappa near 0.0 or negative."""
    y_true = ["NEW", "OPEN_BOX", "DAMAGED", "NEW", "OPEN_BOX", "DAMAGED"]
    y_pred = ["OPEN_BOX", "DAMAGED", "NEW", "OPEN_BOX", "DAMAGED", "NEW"]

    kappa = calculate_cohens_kappa(y_true, y_pred)
    assert kappa <= 0.0


def test_cohens_kappa_direct_and_sklearn_consistency():
    """Direct mathematical formulation matches scikit-learn output."""
    y_true = ["NEW", "NEW", "OPEN_BOX", "DAMAGED", "DAMAGED", "OPEN_BOX"]
    y_pred = ["NEW", "OPEN_BOX", "OPEN_BOX", "DAMAGED", "NEW", "OPEN_BOX"]

    k_sklearn = calculate_cohens_kappa(y_true, y_pred)
    k_direct = direct_cohens_kappa(y_true, y_pred, labels=["NEW", "OPEN_BOX", "DAMAGED"])

    assert abs(k_sklearn - k_direct) < 0.001


def test_cohens_kappa_mismatched_lengths_raises_error():
    """Inputs of unequal length must raise ValueError."""
    with pytest.raises(ValueError):
        calculate_cohens_kappa(["NEW", "OPEN_BOX"], ["NEW"])


def test_confusion_matrix_structure():
    """Confusion matrix accurately counts predictions and computes per-class precision and recall."""
    y_true = ["NEW", "NEW", "OPEN_BOX", "DAMAGED"]
    y_pred = ["NEW", "OPEN_BOX", "OPEN_BOX", "DAMAGED"]
    labels = ["NEW", "OPEN_BOX", "DAMAGED"]

    cm_data = calculate_confusion_matrix_data(y_true, y_pred, labels)

    assert cm_data["labels"] == labels
    matrix = cm_data["matrix"]
    # NEW: 1 predicted NEW (TP=1), 1 predicted OPEN_BOX (FN=1)
    # OPEN_BOX: 1 predicted OPEN_BOX (TP=1)
    # DAMAGED: 1 predicted DAMAGED (TP=1)
    assert matrix[0] == [1, 1, 0]  # Actual NEW
    assert matrix[1] == [0, 1, 0]  # Actual OPEN_BOX
    assert matrix[2] == [0, 0, 1]  # Actual DAMAGED

    per_class = cm_data["per_class"]
    assert per_class["NEW"]["recall"] == 0.5  # 1/2
    assert per_class["NEW"]["precision"] == 1.0  # 1/1
    assert per_class["OPEN_BOX"]["precision"] == 0.5  # 1/2
    assert per_class["OPEN_BOX"]["recall"] == 1.0  # 1/1
    assert per_class["DAMAGED"]["precision"] == 1.0
    assert per_class["DAMAGED"]["recall"] == 1.0
