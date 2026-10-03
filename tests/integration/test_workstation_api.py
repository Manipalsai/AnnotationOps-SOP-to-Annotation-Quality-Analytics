"""
Integration tests for AnnotationOps Workstation HTTP Server (app/annotation/server.py).
Tests the full request-response lifecycle, static serving, and raw file persistence.
"""

from datetime import datetime, timezone
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.annotation.server import app, RAW_DIR


@pytest.fixture
def client():
    return TestClient(app)


def test_serve_index_html(client):
    """Root route / serves the HTML annotation workstation."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "ANNOTATION" in response.text
    assert "OPS" in response.text
    assert "Grade Product Condition" in response.text


def test_get_tasks_manifest(client):
    """GET /api/tasks returns all generated tasks."""
    response = client.get("/api/tasks")
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) >= 120
    assert tasks[0]["task_id"].startswith(("AST-", "TSK-"))


def test_get_spec(client):
    """GET /api/spec returns current YAML specification contract."""
    response = client.get("/api/spec")
    assert response.status_code == 200
    spec = response.json()
    assert "task" in spec
    assert "labels" in spec
    assert spec["labels"] == ["NEW", "OPEN_BOX", "DAMAGED"]


def test_get_image(client):
    """GET /api/images/{filename} returns the image asset."""
    response = client.get("/api/images/img_0001.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_get_nonexistent_image(client):
    """Non-existent image returns 404."""
    response = client.get("/api/images/nonexistent_img.png")
    assert response.status_code == 404


def test_submit_valid_new_annotation(client):
    """POST /api/annotate with valid NEW payload persists raw file and returns 201."""
    payload = {
        "task_id": "TSK-TEST-001",
        "image_id": "img_0001.png",
        "annotator_id": "ANNO-01",
        "condition": "NEW",
        "packaging_condition": None,
        "seal_condition": None,
        "damage_type": None,
        "damage_severity": None,
        "description": None,
        "annotation_timestamp": datetime.now(timezone.utc).isoformat(),
        "processing_time_seconds": 12.4,
        "schema_version": "1.0.0",
    }

    response = client.post("/api/annotate", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "accepted"
    assert "raw_file" in data

    # Verify file was written to data/raw
    raw_path = RAW_DIR / data["raw_file"]
    assert raw_path.exists()

    # Clean up test file
    raw_path.unlink()


def test_submit_valid_damaged_annotation(client):
    """POST /api/annotate with valid DAMAGED payload succeeds."""
    payload = {
        "task_id": "TSK-TEST-002",
        "image_id": "img_0002.png",
        "annotator_id": "ANNO-02",
        "condition": "DAMAGED",
        "packaging_condition": None,
        "seal_condition": None,
        "damage_type": "CRUSHED_BOX",
        "damage_severity": "MODERATE",
        "description": "Right side panel crushed inward 3.5cm.",
        "annotation_timestamp": datetime.now(timezone.utc).isoformat(),
        "processing_time_seconds": 18.2,
        "schema_version": "1.0.0",
    }

    response = client.post("/api/annotate", json=payload)
    assert response.status_code == 201
    data = response.json()
    raw_path = RAW_DIR / data["raw_file"]
    assert raw_path.exists()
    raw_path.unlink()


def test_submit_invalid_conditional_payload_rejected(client):
    """POST /api/annotate with conditional rule violation returns 422."""
    payload = {
        "task_id": "TSK-TEST-003",
        "image_id": "img_0003.png",
        "annotator_id": "ANNO-03",
        "condition": "OPEN_BOX",
        "packaging_condition": "INTACT",
        # missing seal_condition
        "damage_type": None,
        "damage_severity": None,
        "description": None,
        "annotation_timestamp": datetime.now(timezone.utc).isoformat(),
        "processing_time_seconds": 5.0,
        "schema_version": "1.0.0",
    }

    response = client.post("/api/annotate", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "seal_condition" in data["detail"]
