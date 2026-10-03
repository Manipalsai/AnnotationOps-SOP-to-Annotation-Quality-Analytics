"""
Unit tests for Precision, Recall, and F1-Score Quality Science Metrics.
Verifies:
- Precision, recall, and F1 calculations match ground truth formulas
- Macro F1 calculation is correct
- Divide-by-zero safeguards function properly for empty predictions
"""

from pipeline.metrics import calculate_confusion_matrix_data


def test_confusion_matrix_perfect_agreement():
    """When predictions match ground truth 100%, precision, recall, and F1 must all be 1.0."""
    y_true = ["NEW", "OPEN_BOX", "DAMAGED", "NEW", "OPEN_BOX"]
    y_pred = ["NEW", "OPEN_BOX", "DAMAGED", "NEW", "OPEN_BOX"]

    res = calculate_confusion_matrix_data(y_true, y_pred)
    assert res["macro_f1"] == 1.0

    for lbl in ["NEW", "OPEN_BOX", "DAMAGED"]:
        metrics = res["per_class"][lbl]
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
        assert metrics["f1_score"] == 1.0


def test_confusion_matrix_partial_agreement():
    """Verify precision, recall, and F1 calculations on known asymmetric confusion."""
    # 2 NEW, 2 OPEN_BOX, 2 DAMAGED
    y_true = ["NEW", "NEW", "OPEN_BOX", "OPEN_BOX", "DAMAGED", "DAMAGED"]
    # Model predicts 1 NEW correctly, 1 NEW as OPEN_BOX, 2 OPEN_BOX correctly, 2 DAMAGED correctly
    y_pred = ["NEW", "OPEN_BOX", "OPEN_BOX", "OPEN_BOX", "DAMAGED", "DAMAGED"]

    res = calculate_confusion_matrix_data(y_true, y_pred)

    # For NEW: actual=2, pred=1, TP=1 -> recall = 1/2 = 0.5, precision = 1/1 = 1.0
    new_metrics = res["per_class"]["NEW"]
    assert new_metrics["precision"] == 1.0
    assert new_metrics["recall"] == 0.5
    # F1 = 2 * (1.0 * 0.5) / (1.0 + 0.5) = 1.0 / 1.5 = 0.6667
    assert abs(new_metrics["f1_score"] - 0.6667) < 0.001

    # For DAMAGED: actual=2, pred=2, TP=2 -> recall = 1.0, precision = 1.0, F1 = 1.0
    dmg_metrics = res["per_class"]["DAMAGED"]
    assert dmg_metrics["precision"] == 1.0
    assert dmg_metrics["recall"] == 1.0
    assert dmg_metrics["f1_score"] == 1.0


def test_confusion_matrix_zero_predictions_edge_case():
    """Verify divide-by-zero protection when a class has 0 predictions."""
    y_true = ["OPEN_BOX", "OPEN_BOX"]
    y_pred = ["OPEN_BOX", "OPEN_BOX"]

    res = calculate_confusion_matrix_data(y_true, y_pred)
    # NEW has 0 actual and 0 pred
    new_metrics = res["per_class"]["NEW"]
    assert new_metrics["precision"] == 0.0
    assert new_metrics["recall"] == 0.0
    assert new_metrics["f1_score"] == 0.0
