"""
Deterministic Enterprise-Scale Synthetic Dataset Generator — AnnotationOps v2.0
================================================================================
Generates a realistic enterprise-scale synthetic annotation workload.

SYNTHETIC DATA NOTICE:
    All product assets, annotator records, and annotation events in this dataset
    are SYNTHETICALLY GENERATED for portfolio demonstration purposes only.
    They do NOT represent any real products, real people, or real business operations.
    Seed=42 guarantees full reproducibility.

Dataset Target:
    - 5,000 unique synthetic product assets
    - 8 product categories
    - 3 primary conditions (NEW / OPEN_BOX / DAMAGED)
    - 3 difficulty tiers (EASY / MEDIUM / HARD)
    - 4 priority levels (LOW / NORMAL / HIGH / CRITICAL)
    - ~400 gold-standard items (~8% of assets)
    - 200 representative PNG images (covering all condition/category combos)
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = BASE_DIR / "data"

DEFAULT_SEED = 42
DEFAULT_NUM_ASSETS = 5_000
DEFAULT_GOLD_RATIO = 0.08
DEFAULT_IMAGE_SAMPLES = 200

PRODUCT_CATEGORIES = [
    {"name": "Wireless ANC Headphones",    "group": "Audio Products",       "sku_prefix": "AUD", "box_color": (45, 52, 71)},
    {"name": "Smart Fitness Watch",         "group": "Wearables",            "sku_prefix": "WEA", "box_color": (32, 60, 50)},
    {"name": "Ceramic Espresso Grinder",    "group": "Kitchen Appliances",   "sku_prefix": "KIT", "box_color": (60, 42, 35)},
    {"name": "Mechanical Gaming Keyboard",  "group": "Computer Accessories", "sku_prefix": "CAC", "box_color": (40, 40, 45)},
    {"name": "Compact Air Purifier",        "group": "Home Products",        "sku_prefix": "HOM", "box_color": (48, 55, 65)},
    {"name": "Wireless Earbuds Pro",        "group": "Audio Products",       "sku_prefix": "AUD", "box_color": (55, 45, 65)},
    {"name": "Portable Power Bank 20K",     "group": "Personal Devices",     "sku_prefix": "PER", "box_color": (35, 50, 60)},
    {"name": "Smart LED Desk Lamp",         "group": "Home Products",        "sku_prefix": "HOM", "box_color": (50, 55, 45)},
]

CONDITION_WEIGHTS = {"NEW": 0.28, "OPEN_BOX": 0.42, "DAMAGED": 0.30}
DIFFICULTY_WEIGHTS = {"EASY": 0.40, "MEDIUM": 0.40, "HARD": 0.20}
PRIORITY_WEIGHTS   = {"LOW": 0.10, "NORMAL": 0.55, "HIGH": 0.25, "CRITICAL": 0.10}

SUB_TYPES = {
    "NEW":       ["PRISTINE"],
    "OPEN_BOX":  ["BROKEN", "MISSING", "RESEALED"],
    "DAMAGED":   ["CRUSHED_BOX", "TEAR_PUNCTURE", "LIQUID_STAIN", "ITEM_DEFECT"],
}

DMG_DESCRIPTIONS = {
    "CRUSHED_BOX":   "Carton corner collapsed inward with visible buckling and deformation along structural edge.",
    "TEAR_PUNCTURE": "Puncture-tear exceeding 20mm through retail carton front face with exposed interior.",
    "LIQUID_STAIN":  "Dark liquid discoloration and moisture saturation across lower retail packaging surface.",
    "ITEM_DEFECT":   "Internal merchandise exhibits surface hairline fracture along outer plastic casing.",
}


def _weighted_choice(rng: random.Random, weights: dict) -> str:
    keys = list(weights.keys())
    probs = list(weights.values())
    return rng.choices(keys, weights=probs, k=1)[0]


def _build_asset(asset_id: str, idx: int, rng: random.Random, is_gold: bool, img_filename: str) -> dict:
    cat = rng.choice(PRODUCT_CATEGORIES)
    sku = f"{cat['sku_prefix']}-{rng.randint(100, 999):03d}"
    condition = _weighted_choice(rng, CONDITION_WEIGHTS)
    difficulty = _weighted_choice(rng, DIFFICULTY_WEIGHTS)
    priority = _weighted_choice(rng, PRIORITY_WEIGHTS)
    sub_type = rng.choice(SUB_TYPES[condition])

    pkg_cond = seal_cond = dmg_type = dmg_sev = desc = None
    if condition == "OPEN_BOX":
        pkg_cond = rng.choice(["INTACT", "WORN", "MISSING"])
        seal_cond = sub_type
    elif condition == "DAMAGED":
        dmg_type = sub_type
        dmg_sev = rng.choice(["MINOR", "MODERATE", "SEVERE"])
        desc = DMG_DESCRIPTIONS[dmg_type]

    return {
        "asset_id": asset_id,
        "task_id": asset_id,
        "image_id": img_filename,
        "image_path": f"data/images/{img_filename}",
        "product_category": cat["name"],
        "category_group": cat["group"],
        "sku": sku,
        "priority": priority,
        "difficulty": difficulty,
        "ground_truth_condition": condition,
        "ground_truth_packaging_condition": pkg_cond,
        "ground_truth_seal_condition": seal_cond,
        "ground_truth_damage_type": dmg_type,
        "ground_truth_damage_severity": dmg_sev,
        "ground_truth_description": desc,
        "is_gold": is_gold,
        "synthetic": True,
        "seed": DEFAULT_SEED,
    }


def _create_canvas(w: int = 600, h: int = 450) -> tuple:
    img = Image.new("RGB", (w, h), color=(240, 242, 245))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 360, w, h], fill=(218, 222, 228))
    draw.line([0, 360, w, 360], fill=(195, 200, 208), width=2)
    return img, draw


def _watermark(draw: ImageDraw.ImageDraw, w: int, seed: int):
    draw.rectangle([0, 0, w, 24], fill=(30, 30, 35))
    draw.text((12, 5), f"SYNTHETIC FIXTURE — SEED {seed} — NOT ACTUAL PRODUCT DATA", fill=(220, 220, 225))


def _render_box(draw, x, y, w, h, cat_name, sku, box_color, condition, sub_type, rng):
    draw.rectangle([x, y, x+w, y+h], fill=box_color, outline=(20, 20, 25), width=2)
    lid = [(x, y), (x+40, y-30), (x+w+40, y-30), (x+w, y)]
    draw.polygon(lid, fill=tuple(min(255, c+25) for c in box_color), outline=(20, 20, 25))
    side = [(x+w, y), (x+w+40, y-30), (x+w+40, y+h-30), (x+w, y+h)]
    draw.polygon(side, fill=tuple(max(0, c-25) for c in box_color), outline=(20, 20, 25))
    draw.rectangle([x+20, y+20, x+w-20, y+70], fill=(255, 255, 255))
    draw.text((x+30, y+28), cat_name[:22].upper(), fill=(20, 20, 20))
    draw.text((x+30, y+48), f"SKU: {sku}", fill=(100, 100, 105))
    draw.rectangle([x+40, y+90, x+w-40, y+h-40], fill=(230, 233, 238), outline=(180, 185, 195))

    if condition == "NEW":
        sx = x + w//2 - 25
        draw.rectangle([sx, y-10, sx+50, y+10], fill=(46, 125, 50), outline=(27, 94, 32))
        draw.text((sx+6, y-6), "SEALED", fill=(255, 255, 255))
    elif condition == "OPEN_BOX":
        sx = x + w//2 - 25
        if sub_type == "BROKEN":
            draw.rectangle([sx, y-10, sx+22, y+10], fill=(198, 40, 40))
            draw.rectangle([sx+28, y-10, sx+50, y+10], fill=(198, 40, 40))
            draw.text((sx+2, y+15), "[SEAL BROKEN]", fill=(198, 40, 40))
        elif sub_type == "RESEALED":
            draw.rectangle([sx-10, y-12, sx+60, y+12], fill=(240, 240, 180), outline=(180, 180, 100))
            draw.text((sx-5, y+15), "[RE-TAPED]", fill=(180, 130, 20))
        else:
            draw.rectangle([sx, y-10, sx+50, y+10], fill=(220, 220, 220), outline=(160, 160, 160))
            draw.text((sx+2, y+15), "[NO SEAL]", fill=(120, 120, 120))
        draw.line([x+30, y-2, x+120, y-15], fill=(20, 20, 20), width=3)
    elif condition == "DAMAGED":
        if sub_type == "CRUSHED_BOX":
            poly = [(x, y+120), (x+50, y+100), (x+75, y+170), (x+30, y+210), (x, y+190)]
            draw.polygon(poly, fill=(30, 30, 30), outline=(180, 40, 40), width=2)
            draw.line([x+10, y+110, x+65, y+195], fill=(220, 50, 50), width=3)
            draw.text((x+10, y+220), "! CRUSH DEFORMATION !", fill=(180, 20, 20))
        elif sub_type == "TEAR_PUNCTURE":
            poly = [(x+80, y+130), (x+150, y+110), (x+170, y+160), (x+120, y+180), (x+70, y+150)]
            draw.polygon(poly, fill=(15, 15, 18), outline=(220, 20, 20), width=3)
            draw.text((x+70, y+190), "! CARTON PUNCTURE !", fill=(200, 20, 20))
        elif sub_type == "LIQUID_STAIN":
            stain = [(x+40, y+120), (x+180, y+110), (x+220, y+200), (x+90, y+230), (x+20, y+180)]
            draw.polygon(stain, fill=(90, 75, 55), outline=(130, 110, 80))
            draw.text((x+40, y+240), "! LIQUID SATURATION !", fill=(140, 90, 20))
        else:
            draw.line([x+60, y+110, x+180, y+190], fill=(220, 20, 20), width=4)
            draw.line([x+180, y+190, x+160, y+230], fill=(220, 20, 20), width=3)
            draw.text((x+60, y+240), "! ITEM FRACTURE !", fill=(200, 20, 20))


def _generate_images(images_dir: Path, num_samples: int, seed: int, rng: random.Random):
    images_dir.mkdir(parents=True, exist_ok=True)
    box_map = {c["name"]: c["box_color"] for c in PRODUCT_CATEGORIES}
    conditions = ["NEW", "OPEN_BOX", "DAMAGED"]
    sub_defaults = {"NEW": "PRISTINE", "OPEN_BOX": "BROKEN", "DAMAGED": "CRUSHED_BOX"}
    idx = 0
    for cat in PRODUCT_CATEGORIES:
        for cond in conditions:
            if idx >= num_samples:
                return
            fn = images_dir / f"img_{idx+1:05d}.png"
            if not fn.exists():
                img, draw = _create_canvas()
                _watermark(draw, 600, seed)
                _render_box(draw, 130, 80, 260, 270, cat["name"], f"{cat['sku_prefix']}-000",
                            cat["box_color"], cond, sub_defaults[cond], rng)
                img.save(fn, "PNG")
            idx += 1
    # Fill remaining with variations
    for i in range(idx, num_samples):
        fn = images_dir / f"img_{i+1:05d}.png"
        if not fn.exists():
            cat = PRODUCT_CATEGORIES[i % len(PRODUCT_CATEGORIES)]
            cond = conditions[i % 3]
            sub_types_list = SUB_TYPES[cond]
            sub = sub_types_list[i % len(sub_types_list)]
            img, draw = _create_canvas()
            _watermark(draw, 600, seed)
            _render_box(draw, 130, 80, 260, 270, cat["name"],
                        f"{cat['sku_prefix']}-{i%999:03d}", cat["box_color"], cond, sub, rng)
            img.save(fn, "PNG")


def generate_synthetic_dataset(
    output_dir: str = "data",
    num_assets: int = DEFAULT_NUM_ASSETS,
    gold_ratio: float = DEFAULT_GOLD_RATIO,
    num_image_samples: int = DEFAULT_IMAGE_SAMPLES,
    seed: int = DEFAULT_SEED,
    num_tasks: int | None = None,
) -> tuple[int, int]:
    """
    Generate deterministic synthetic asset catalog, task manifest, and gold set.
    Returns: (total_tasks, gold_count)
    """
    if num_tasks is not None:
        num_assets = num_tasks
    rng = random.Random(seed)
    base_path = Path(output_dir)
    if not base_path.is_absolute():
        base_path = (BASE_DIR / base_path).resolve()
    images_dir = base_path / "images"
    gold_dir = base_path / "gold"
    gold_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Generator] Building {num_assets:,} synthetic assets (seed={seed})...")
    target_gold = int(num_assets * gold_ratio)
    gold_stride = max(1, num_assets // target_gold)

    assets = []
    gold_count = 0
    for i in range(num_assets):
        asset_id = f"AST-{i+1:05d}"
        is_gold = (i % gold_stride == 0) and (gold_count < target_gold)
        if is_gold:
            gold_count += 1
        # Cycle through representative image filenames
        img_idx = (i % num_image_samples) + 1
        img_filename = f"img_{img_idx:05d}.png"
        assets.append(_build_asset(asset_id, i, rng, is_gold, img_filename))

    # Render representative images
    print(f"[Generator] Rendering {num_image_samples} representative PNG images...")
    _generate_images(images_dir, num_image_samples, seed, rng)
    print(f"[Generator] Images saved to {images_dir}")

    # Write task manifest
    manifest = []
    gold_records = []
    for asset in assets:
        manifest.append({
            "task_id": asset["task_id"],
            "image_id": asset["image_id"],
            "image_path": asset["image_path"],
            "product_category": asset["product_category"],
            "category_group": asset["category_group"],
            "sku": asset["sku"],
            "priority": asset["priority"],
            "difficulty": asset["difficulty"],
            "synthetic": True,
            "seed": seed,
        })
        if asset["is_gold"]:
            gold_records.append({
                "task_id": asset["task_id"],
                "image_id": asset["image_id"],
                "ground_truth_condition": asset["ground_truth_condition"],
                "ground_truth_packaging_condition": asset["ground_truth_packaging_condition"],
                "ground_truth_seal_condition": asset["ground_truth_seal_condition"],
                "ground_truth_damage_type": asset["ground_truth_damage_type"],
                "ground_truth_damage_severity": asset["ground_truth_damage_severity"],
                "ground_truth_description": asset["ground_truth_description"],
                "difficulty": asset["difficulty"],
                "verified_by": "Lead Quality Science Analyst (Synthetic)",
                "synthetic": True,
            })

    manifest_file = base_path / "manifest_tasks.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, separators=(",", ":"))

    gold_file = gold_dir / "gold_annotations.json"
    with open(gold_file, "w", encoding="utf-8") as f:
        json.dump(gold_records, f, separators=(",", ":"))

    print(f"[Generator] {len(manifest):,} tasks -> {manifest_file}")
    print(f"[Generator] {len(gold_records):,} gold records -> {gold_file}")
    return len(manifest), len(gold_records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AnnotationOps v2 Enterprise Dataset Generator")
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--num-assets", type=int, default=DEFAULT_NUM_ASSETS)
    parser.add_argument("--gold-ratio", type=float, default=DEFAULT_GOLD_RATIO)
    parser.add_argument("--image-samples", type=int, default=DEFAULT_IMAGE_SAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    generate_synthetic_dataset(
        args.output_dir, args.num_assets, args.gold_ratio, args.image_samples, args.seed
    )
