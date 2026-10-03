"""
Unit tests for SQL Analytics Repository.
Verifies that all 25 queries across operational_metrics.sql, annotator_metrics.sql,
quality_science.sql, and data_quality_audit.sql execute validly on the SQLite database.
"""

import re
import sqlite3
from pathlib import Path
from pipeline.database import DEFAULT_DB_PATH

SQL_DIR = Path("sql")


def test_all_sql_queries_execute_successfully():
    """Execute every SQL statement in sql/ directory against the live warehouse database."""
    assert DEFAULT_DB_PATH.exists(), "Database file must exist to run SQL tests"
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))

    sql_files = [
        "operational_metrics.sql",
        "annotator_metrics.sql",
        "quality_science.sql",
        "data_quality_audit.sql",
    ]

    total_queries_executed = 0

    for fname in sql_files:
        fpath = SQL_DIR / fname
        assert fpath.exists(), f"SQL file {fname} not found"

        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        # Remove line comments
        clean_content = re.sub(r"--.*", "", content)
        statements = [s.strip() for s in clean_content.split(";") if s.strip()]

        assert len(statements) >= 3, f"{fname} should contain at least 3 distinct queries, got {len(statements)}"

        for idx, stmt in enumerate(statements):
            cursor = conn.cursor()
            try:
                cursor.execute(stmt)
                rows = cursor.fetchall()
                # Ensure query ran and produced a valid result
                assert rows is not None, f"Query {idx+1} in {fname} returned None"
                total_queries_executed += 1
            except Exception as exc:
                conn.close()
                raise AssertionError(f"Failed to execute Query {idx+1} in {fname}:\n{stmt}\nError: {exc}")

    conn.close()
    assert total_queries_executed >= 20, f"Expected >= 20 SQL queries executed, got {total_queries_executed}"
