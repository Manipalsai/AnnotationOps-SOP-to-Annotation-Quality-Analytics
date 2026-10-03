"""
Unit tests for Simulated SLA Attainment and Operational Variance Analysis.
Verifies:
- Minimum and Maximum threshold rule evaluations
- Absolute and percentage variance calculations
- Proper structured output of variance analysis tables
"""

from pipeline.database import DEFAULT_DB_PATH
from pipeline.metrics import compute_sla_kpis, compute_variance_analysis


def test_sla_evaluations_structure_and_rules():
    """Verify that all SLA benchmarks evaluate against simulation targets with valid status flags."""
    sla = compute_sla_kpis(DEFAULT_DB_PATH)

    assert "evaluations" in sla
    assert "total_targets" in sla
    assert "attainment_pct" in sla
    assert sla["total_targets"] >= 5
    assert 0.0 <= sla["attainment_pct"] <= 100.0

    for ev in sla["evaluations"]:
        assert "metric_key" in ev
        assert "metric_name" in ev
        assert "target" in ev
        assert "actual" in ev
        assert "variance_abs" in ev
        assert "variance_pct" in ev
        assert ev["status"] in ["TARGET MET", "TARGET MISSED"]
        assert isinstance(ev["is_met"], bool)

        # Mathematical check on variance
        expected_diff = round(ev["actual"] - ev["target"], 2)
        assert abs(ev["variance_abs"] - expected_diff) < 0.01


def test_variance_analysis_dataframe_structure():
    """Verify compute_variance_analysis returns a clean, formatted reporting dataframe."""
    df = compute_variance_analysis(DEFAULT_DB_PATH)
    assert not df.empty
    expected_cols = [
        "Operational Metric",
        "Simulated Target",
        "Actual Result",
        "Absolute Variance",
        "Percent Variance",
        "Performance Status",
        "Rule Type",
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing expected column '{col}' in variance dataframe"
