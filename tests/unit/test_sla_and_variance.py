"""
Unit tests for SLA Attainment and Operational Variance Analysis.
Uses self-contained test DB fixture — no pre-generated files required.
"""

from pipeline.metrics import compute_sla_kpis, compute_variance_analysis


def test_sla_evaluations_structure_and_rules(test_db_path):
    sla = compute_sla_kpis(test_db_path)
    assert "evaluations" in sla
    assert "total_targets" in sla
    assert "attainment_pct" in sla
    assert sla["total_targets"] >= 5
    assert 0.0 <= sla["attainment_pct"] <= 100.0
    for ev in sla["evaluations"]:
        assert ev["status"] in ["TARGET MET", "TARGET MISSED"]
        assert isinstance(ev["is_met"], bool)
        expected_diff = round(ev["actual"] - ev["target"], 2)
        assert abs(ev["variance_abs"] - expected_diff) < 0.01


def test_variance_analysis_dataframe_structure(test_db_path):
    df = compute_variance_analysis(test_db_path)
    assert not df.empty
    for col in ["Operational Metric", "Simulated Target", "Actual Result",
                "Absolute Variance", "Percent Variance", "Performance Status", "Rule Type"]:
        assert col in df.columns
