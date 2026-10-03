"""
Unit tests for SQL Analytics Repository.
Uses a self-contained test DB (no pre-generated files needed).
"""

import re
import sqlite3
from pathlib import Path
import pytest

SQL_DIR = Path("sql")


def test_all_sql_queries_execute_successfully(test_db_path):
    """Execute every SQL statement in sql/ against the self-contained test warehouse."""
    conn = sqlite3.connect(str(test_db_path))

    sql_files = [
        "operational_metrics.sql",
        "annotator_metrics.sql",
        "quality_science.sql",
        "data_quality_audit.sql",
    ]

    total_executed = 0

    for fname in sql_files:
        fpath = SQL_DIR / fname
        assert fpath.exists(), f"SQL file {fname} not found"

        clean = re.sub(r"--.*", "", fpath.read_text(encoding="utf-8"))
        statements = [s.strip() for s in clean.split(";") if s.strip()]

        assert len(statements) >= 3, f"{fname} should have >= 3 queries"

        for idx, stmt in enumerate(statements):
            try:
                rows = conn.execute(stmt).fetchall()
                assert rows is not None
                total_executed += 1
            except Exception as exc:
                conn.close()
                raise AssertionError(f"Query {idx+1} in {fname} failed:\n{stmt}\nError: {exc}")

    conn.close()
    assert total_executed >= 20, f"Expected >= 20 queries executed, got {total_executed}"
