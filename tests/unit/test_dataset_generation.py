"""
Unit tests for Dataset Engine and Gold Standard Baseline (scripts/generate_dataset.py).
Verifies:
- Dataset generation is deterministic with fixed seed.
- Generated image files exist, are valid, and have expected dimensions.
- Gold annotations conform strictly to GoldRecord schema and conditional rules.
- Explicit synthetic markers are present.
"""

import json
from pathlib import Path
from PIL import Image

from schemas.models import GoldRecord, PrimaryCondition
from scripts.generate_dataset import generate_synthetic_dataset


def test_manifest_and_gold_files_exist():
    """Verify that dataset manifest and gold benchmark files exist on disk."""
    manifest_path = Path("data/manifest_tasks.json")
    gold_path = Path("data/gold/gold_annotations.json")

    assert manifest_path.exists(), "Manifest file missing"
    assert gold_path.exists(), "Gold annotations file missing"

    with open(manifest_path, "r", encoding="utf-8") as f:
        tasks = json.load(f)
    with open(gold_path, "r", encoding="utf-8") as f:
        gold = json.load(f)

    assert len(tasks) == 120, f"Expected 120 tasks, got {len(tasks)}"
    assert len(gold) == 30, f"Expected 30 gold items, got {len(gold)}"


def test_generated_images_integrity():
    """Check a sample of generated images for visual file integrity and dimensions."""
    images_dir = Path("data/images")
    assert images_dir.exists(), "Images directory missing"

    # Test first 10 images
    for i in range(1, 11):
        img_path = images_dir / f"img_{i:04d}.png"
        assert img_path.exists(), f"Image {img_path} not found"
        with Image.open(img_path) as img:
            assert img.size == (600, 450)
            assert img.format == "PNG"


def test_gold_records_conform_to_schema():
    """Every record in data/gold/gold_annotations.json must be a valid GoldRecord."""
    gold_path = Path("data/gold/gold_annotations.json")
    with open(gold_path, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    for item in gold_data:
        # Pydantic validation
        record = GoldRecord(**item)
        assert record.synthetic is True

        # SOP conditional validation check on gold ground truth
        if record.ground_truth_condition == PrimaryCondition.NEW:
            assert record.ground_truth_packaging_condition is None
            assert record.ground_truth_seal_condition is None
            assert record.ground_truth_damage_type is None
            assert record.ground_truth_damage_severity is None
            assert record.ground_truth_description is None
        elif record.ground_truth_condition == PrimaryCondition.OPEN_BOX:
            assert record.ground_truth_packaging_condition is not None
            assert record.ground_truth_seal_condition is not None
            assert record.ground_truth_damage_type is None
            assert record.ground_truth_damage_severity is None
            assert record.ground_truth_description is None
        elif record.ground_truth_condition == PrimaryCondition.DAMAGED:
            assert record.ground_truth_damage_type is not None
            assert record.ground_truth_damage_severity is not None
            assert record.ground_truth_description is not None
            assert record.ground_truth_packaging_condition is None
            assert record.ground_truth_seal_condition is None


def test_dataset_generation_is_deterministic(tmp_path):
    """Running generator twice with seed=42 produces bitwise identical task metadata."""
    dir1 = tmp_path / "run1"
    dir2 = tmp_path / "run2"

    n1_tasks, n1_gold = generate_synthetic_dataset(str(dir1), num_tasks=20, seed=42)
    n2_tasks, n2_gold = generate_synthetic_dataset(str(dir2), num_tasks=20, seed=42)

    assert n1_tasks == n2_tasks == 20
    assert n1_gold == n2_gold == 5

    with open(dir1 / "manifest_tasks.json", "r", encoding="utf-8") as f1:
        data1 = json.load(f1)
    with open(dir2 / "manifest_tasks.json", "r", encoding="utf-8") as f2:
        data2 = json.load(f2)

    assert data1 == data2, "Non-deterministic task generation detected!"
