"""
AnnotationOps Workstation HTTP Server
Provides REST API endpoints and static file hosting for human annotation operations.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
import uvicorn
import yaml

from schemas.models import AnnotationRecord

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
IMAGES_DIR = DATA_DIR / "images"
MANIFEST_FILE = DATA_DIR / "manifest_tasks.json"
SPEC_FILE = BASE_DIR / "schemas" / "annotation.yaml"

# Ensure directories exist
RAW_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


async def serve_index(request: Request) -> Response:
    """Serve the workstation single-page HTML interface."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse({"error": "Workstation UI not built."}, status_code=404)
    return FileResponse(index_file)


async def get_tasks(request: Request) -> Response:
    """Return task list from manifest."""
    if not MANIFEST_FILE.exists():
        return JSONResponse({"error": "Task manifest not generated."}, status_code=404)
    try:
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            tasks = json.load(f)
        return JSONResponse(tasks)
    except Exception as e:
        return JSONResponse({"error": f"Failed reading manifest: {e}"}, status_code=500)


async def get_image(request: Request) -> Response:
    """Serve a specific product image by filename."""
    filename = request.path_params["filename"]
    # Path traversal safety check
    safe_path = (IMAGES_DIR / filename).resolve()
    if not str(safe_path).startswith(str(IMAGES_DIR.resolve())) or not safe_path.exists():
        return JSONResponse({"error": "Image not found."}, status_code=404)
    return FileResponse(safe_path)


async def get_spec(request: Request) -> Response:
    """Return current YAML specification contract as JSON."""
    if not SPEC_FILE.exists():
        return JSONResponse({"error": "Specification not found."}, status_code=404)
    with open(SPEC_FILE, "r", encoding="utf-8") as f:
        spec_data = yaml.safe_load(f)
    return JSONResponse(spec_data)


async def submit_annotation(request: Request) -> Response:
    """
    Ingest human annotation payload, validate via Pydantic contract,
    and persist directly into immutable raw staging directory.
    """
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid JSON body."}, status_code=400)

    # 1. Pydantic schema & conditional rule validation
    try:
        validated_record = AnnotationRecord(**payload)
    except ValidationError as exc:
        error_msg = exc.errors()[0]["msg"]
        serializable_errors = [
            {"loc": list(err.get("loc", [])), "msg": str(err.get("msg", "")), "type": str(err.get("type", ""))}
            for err in exc.errors()
        ]
        return JSONResponse({"detail": str(error_msg), "errors": serializable_errors}, status_code=422)

    # 2. Persist to immutable raw staging sink
    task_id = validated_record.task_id
    annotator_id = validated_record.annotator_id
    ts_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    filename = f"{task_id}_{annotator_id}_{ts_str}.json"
    raw_file_path = RAW_DIR / filename

    try:
        with open(raw_file_path, "w", encoding="utf-8") as f:
            f.write(validated_record.model_dump_json(indent=2))
    except Exception as e:
        return JSONResponse({"detail": f"Failed to persist raw record: {e}"}, status_code=500)

    return JSONResponse(
        {
            "status": "accepted",
            "message": f"Annotation for {task_id} received and staged.",
            "task_id": task_id,
            "raw_file": filename,
        },
        status_code=201,
    )


routes = [
    Route("/", serve_index, methods=["GET"]),
    Route("/api/tasks", get_tasks, methods=["GET"]),
    Route("/api/images/{filename:str}", get_image, methods=["GET"]),
    Route("/api/spec", get_spec, methods=["GET"]),
    Route("/api/annotate", submit_annotation, methods=["POST"]),
    Mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static"),
]

app = Starlette(debug=True, routes=routes)


def start_server(host: str = "127.0.0.1", port: int = 8000):
    """Run uvicorn server."""
    print(f"Starting AnnotationOps Workstation on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AnnotationOps Workstation Server")
    parser.add_argument("--host", default="127.0.0.1", help="Binding host")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    args = parser.parse_args()

    start_server(host=args.host, port=args.port)
