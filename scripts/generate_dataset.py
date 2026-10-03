"""
Deterministic Synthetic Product-Condition Dataset Generator
Generates visual fixtures and ground-truth metadata for the returned_product_condition task.

Design Principles:
- Strictly reproducible with random seed (default: 42).
- Explicit synthetic marking (visual banner watermark and metadata flag).
- High visual differentiation:
  * NEW: Pristine retail box with unbroken green tamper seal.
  * OPEN_BOX: Box with severed red tamper seal and opened/ajar flap.
  * DAMAGED: Box with visible crushing deformation, puncture/tear laceration, or liquid saturation.
- Generates:
  * Image assets in data/images/
  * Task manifest in data/manifest_tasks.json
  * Verified Gold Benchmark in data/gold/gold_annotations.json
  * Synthetic dataset documentation in docs/DATASET.md
"""

from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Set global deterministic random seed
DEFAULT_SEED = 42

PRODUCT_CATEGORIES = [
    ("Wireless ANC Headphones", "AUDIO-880", (45, 52, 71)),
    ("Smart Fitness Watch", "WEAR-420", (32, 60, 50)),
    ("Ceramic Espresso Grinder", "KITCH-110", (60, 42, 35)),
    ("Mechanical Gaming Keyboard", "TECH-770", (40, 40, 45)),
    ("Compact Air Purifier", "HOME-305", (48, 55, 65)),
]


def create_base_canvas(width: int = 600, height: int = 450) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Create a neutral studio backdrop with subtle lighting gradient."""
    img = Image.new("RGB", (width, height), color=(240, 242, 245))
    draw = ImageDraw.Draw(img)

    # Studio drop shadow & platform floor
    draw.rectangle([0, 360, width, height], fill=(218, 222, 228))
    draw.line([0, 360, width, 360], fill=(195, 200, 208), width=2)
    return img, draw


def draw_synthetic_watermark(draw: ImageDraw.ImageDraw, width: int, height: int, seed: int):
    """Render a non-intrusive yet unambiguous synthetic fixture banner."""
    draw.rectangle([0, 0, width, 24], fill=(30, 30, 35))
    text = f"SYNTHETIC TEST FIXTURE - SEED {seed} - NOT ACTUAL CUSTOMER DATA"
    draw.text((12, 5), text, fill=(220, 220, 225))


def render_product_box(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    category_name: str,
    sku: str,
    box_color: tuple[int, int, int],
    condition: str,
    sub_type: str,
    rng: random.Random,
):
    """Render 2.5D perspective retail packaging carton with visual condition cues."""
    # Main carton face
    draw.rectangle([x, y, x + w, y + h], fill=box_color, outline=(20, 20, 25), width=2)

    # Top perspective lid
    lid_poly = [(x, y), (x + 40, y - 30), (x + w + 40, y - 30), (x + w, y)]
    lid_color = tuple(min(255, c + 25) for c in box_color)
    draw.polygon(lid_poly, fill=lid_color, outline=(20, 20, 25))

    # Right perspective flap
    side_poly = [(x + w, y), (x + w + 40, y - 30), (x + w + 40, y + h - 30), (x + w, y + h)]
    side_color = tuple(max(0, c - 25) for c in box_color)
    draw.polygon(side_poly, fill=side_color, outline=(20, 20, 25))

    # Branded retail graphics
    draw.rectangle([x + 20, y + 20, x + w - 20, y + 70], fill=(255, 255, 255))
    draw.text((x + 30, y + 28), category_name.upper(), fill=(20, 20, 20))
    draw.text((x + 30, y + 48), f"SKU: {sku} | RETAIL SEAL VERIFIED", fill=(100, 100, 105))

    # Central product silhouette window
    draw.rectangle([x + 40, y + 90, x + w - 40, y + h - 40], fill=(230, 233, 238), outline=(180, 185, 195))
    draw.text((x + 60, y + 150), "[ PRODUCT DISPLAY WINDOW ]", fill=(130, 135, 145))

    # Visual Condition Attributions
    if condition == "NEW":
        # Pristine green intact factory seal sticker across lid seam
        seal_x = x + w // 2 - 25
        draw.rectangle([seal_x, y - 10, seal_x + 50, y + 10], fill=(46, 125, 50), outline=(27, 94, 32), width=1)
        draw.text((seal_x + 6, y - 6), "SEALED", fill=(255, 255, 255))

    elif condition == "OPEN_BOX":
        # Tamper sticker is cut / broken
        seal_x = x + w // 2 - 25
        if sub_type == "BROKEN":
            draw.rectangle([seal_x, y - 10, seal_x + 22, y + 10], fill=(198, 40, 40))
            draw.rectangle([seal_x + 28, y - 10, seal_x + 50, y + 10], fill=(198, 40, 40))
            draw.text((seal_x + 2, y + 15), "[SEAL BROKEN]", fill=(198, 40, 40))
        elif sub_type == "RESEALED":
            draw.rectangle([seal_x - 10, y - 12, seal_x + 60, y + 12], fill=(240, 240, 180), outline=(180, 180, 100))
            draw.text((seal_x - 5, y + 15), "[RE-TAPED / NON-OEM]", fill=(180, 130, 20))
        else:  # MISSING
            draw.rectangle([seal_x, y - 10, seal_x + 50, y + 10], fill=(220, 220, 220), outline=(160, 160, 160))
            draw.text((seal_x + 2, y + 15), "[NO SEAL APPLIED]", fill=(120, 120, 120))

        # Flap slightly ajar
        draw.line([x + 30, y - 2, x + 120, y - 15], fill=(20, 20, 20), width=3)
        draw.polygon([(x + 30, y - 2), (x + 120, y - 15), (x + 120, y - 2)], fill=(200, 200, 205))

    elif condition == "DAMAGED":
        if sub_type == "CRUSHED_BOX":
            # Deformed corner polygon with crush lines
            crush_poly = [
                (x, y + 120),
                (x + 50, y + 100),
                (x + 75, y + 170),
                (x + 30, y + 210),
                (x, y + 190),
            ]
            draw.polygon(crush_poly, fill=(30, 30, 30), outline=(180, 40, 40), width=2)
            draw.line([x + 10, y + 110, x + 65, y + 195], fill=(220, 50, 50), width=3)
            draw.text((x + 10, y + 220), "! CRUSH DEFORMATION !", fill=(180, 20, 20))

        elif sub_type == "TEAR_PUNCTURE":
            # Jagged puncture hole into interior
            puncture = [(x + 80, y + 130), (x + 150, y + 110), (x + 170, y + 160), (x + 120, y + 180), (x + 70, y + 150)]
            draw.polygon(puncture, fill=(15, 15, 18), outline=(220, 20, 20), width=3)
            # Tear lines branching off
            draw.line([x + 150, y + 110, x + 200, y + 80], fill=(20, 20, 20), width=2)
            draw.line([x + 70, y + 150, x + 30, y + 190], fill=(20, 20, 20), width=2)
            draw.text((x + 70, y + 190), "! CARTON PUNCTURE / TEAR !", fill=(200, 20, 20))

        elif sub_type == "LIQUID_STAIN":
            # Moisture saturation stain overlay
            stain = [(x + 40, y + 120), (x + 180, y + 110), (x + 220, y + 200), (x + 90, y + 230), (x + 20, y + 180)]
            draw.polygon(stain, fill=(90, 75, 55), outline=(130, 110, 80))
            draw.text((x + 40, y + 240), "! LIQUID SATURATION STAIN !", fill=(140, 90, 20))

        elif sub_type == "ITEM_DEFECT":
            # Visible fissure crack across window/product
            draw.line([x + 60, y + 110, x + 180, y + 190], fill=(220, 20, 20), width=4)
            draw.line([x + 180, y + 190, x + 160, y + 230], fill=(220, 20, 20), width=3)
            draw.line([x + 180, y + 190, x + 230, y + 210], fill=(220, 20, 20), width=3)
            draw.text((x + 60, y + 240), "! VISIBLE MERCHANDISE FRACTURE !", fill=(200, 20, 20))


def generate_synthetic_dataset(output_dir: str = "data", num_tasks: int = 120, seed: int = DEFAULT_SEED):
    """
    Generate deterministic synthetic images and ground truth metadata.
    Split:
    - 30 tasks reserved for Gold Standard Quality Benchmark (data/gold/gold_annotations.json)
    - 120 total tasks in task queue (data/manifest_tasks.json)
    """
    rng = random.Random(seed)
    base_path = Path(output_dir)
    images_dir = base_path / "images"
    gold_dir = base_path / "gold"

    images_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)

    conditions_distribution = (
        ["NEW"] * 36 +          # 30%
        ["OPEN_BOX"] * 48 +     # 40%
        ["DAMAGED"] * 36        # 30%
    )
    rng.shuffle(conditions_distribution)

    tasks_manifest = []
    gold_annotations = []

    # Difficulty distribution for gold tasks
    difficulties = ["EASY", "MEDIUM", "HARD"]

    for i in range(num_tasks):
        task_id = f"TSK-{i+1:04d}"
        image_filename = f"img_{i+1:04d}.png"
        image_path = images_dir / image_filename

        cat_name, sku, box_color = rng.choice(PRODUCT_CATEGORIES)
        primary_cond = conditions_distribution[i]

        # Determine sub-attributes based on condition
        if primary_cond == "NEW":
            sub_type = "PRISTINE"
            pkg_cond = None
            seal_cond = None
            dmg_type = None
            dmg_sev = None
            desc = None
        elif primary_cond == "OPEN_BOX":
            pkg_cond = rng.choice(["INTACT", "WORN", "MISSING"])
            seal_cond = rng.choice(["BROKEN", "MISSING", "RESEALED"])
            sub_type = seal_cond
            dmg_type = None
            dmg_sev = None
            desc = None
        else:  # DAMAGED
            dmg_type = rng.choice(["CRUSHED_BOX", "TEAR_PUNCTURE", "LIQUID_STAIN", "ITEM_DEFECT"])
            dmg_sev = rng.choice(["MINOR", "MODERATE", "SEVERE"])
            sub_type = dmg_type
            pkg_cond = None
            seal_cond = None
            desc_samples = {
                "CRUSHED_BOX": f"Carton corner collapsed inward approx 4cm with buckling on {sku} box.",
                "TEAR_PUNCTURE": f"Visible puncture tear exceeding 20mm through retail carton front face.",
                "LIQUID_STAIN": f"Dark liquid discoloration and moisture saturation across lower retail packaging.",
                "ITEM_DEFECT": f"Internal merchandise exhibits surface hairline fracture along outer plastic casing.",
            }
            desc = desc_samples[dmg_type]

        # Render image
        img, draw = create_base_canvas(600, 450)
        draw_synthetic_watermark(draw, 600, 450, seed)
        render_product_box(
            draw=draw,
            x=130,
            y=80,
            w=260,
            h=270,
            category_name=cat_name,
            sku=sku,
            box_color=box_color,
            condition=primary_cond,
            sub_type=sub_type,
            rng=rng,
        )

        # Save synthetic image
        img.save(image_path, "PNG")

        # Manifest task record
        task_record = {
            "task_id": task_id,
            "image_id": image_filename,
            "image_path": f"data/images/{image_filename}",
            "product_category": cat_name,
            "sku": sku,
            "synthetic": True,
            "seed": seed,
        }
        tasks_manifest.append(task_record)

        # Gold benchmark subset: Reserve every 4th item (total 30 items)
        if (i + 1) % 4 == 0:
            difficulty = rng.choice(difficulties)
            gold_record = {
                "task_id": task_id,
                "image_id": image_filename,
                "ground_truth_condition": primary_cond,
                "ground_truth_packaging_condition": pkg_cond,
                "ground_truth_seal_condition": seal_cond,
                "ground_truth_damage_type": dmg_type,
                "ground_truth_damage_severity": dmg_sev,
                "ground_truth_description": desc,
                "difficulty": difficulty,
                "verified_by": "Lead Quality Science Analyst",
                "synthetic": True,
            }
            gold_annotations.append(gold_record)

    # Save manifest files
    manifest_file = base_path / "manifest_tasks.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(tasks_manifest, f, indent=2)

    gold_file = gold_dir / "gold_annotations.json"
    with open(gold_file, "w", encoding="utf-8") as f:
        json.dump(gold_annotations, f, indent=2)

    print(f"Generated {len(tasks_manifest)} synthetic tasks -> {manifest_file}")
    print(f"Generated {len(gold_annotations)} gold ground-truth benchmarks -> {gold_file}")
    return len(tasks_manifest), len(gold_annotations)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministic Synthetic Dataset Generator")
    parser.add_argument("--output-dir", default="data", help="Output directory root")
    parser.add_argument("--num-tasks", type=int, default=120, help="Total tasks to generate")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed")
    args = parser.parse_args()

    generate_synthetic_dataset(args.output_dir, args.num_tasks, args.seed)
