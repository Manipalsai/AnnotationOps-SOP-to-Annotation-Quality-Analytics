# Dataset Documentation: Returned Product Condition Annotation Fixtures

**Status:** Synthetic Demonstration Dataset  
**Generator:** `scripts/generate_dataset.py`  
**Random Seed:** `42` (Deterministic)  
**Task Domain:** E-Commerce Returned Merchandise Grading  

---

## 1. Transparency & Anti-Fabrication Notice

> [!IMPORTANT]
> **This dataset is 100% synthetic.**
> It was programmatically generated using Python Pillow specifically for reproducible demonstration, testing, and portfolio evaluation of an Annotation Operations pipeline.
> 
> - It does **not** represent real Amazon or e-commerce customer return data.
> - No proprietary images or private personal identifiable information (PII) are included.
> - Every visual asset contains an explicit banner watermark: `SYNTHETIC TEST FIXTURE - SEED 42 - NOT ACTUAL CUSTOMER DATA`.

---

## 2. Dataset Design & Class Stratification

The dataset comprises **120 tasks** across 5 representative e-commerce consumer goods categories:
- Wireless ANC Headphones (`AUDIO-880`)
- Smart Fitness Watch (`WEAR-420`)
- Ceramic Espresso Grinder (`KITCH-110`)
- Mechanical Gaming Keyboard (`TECH-770`)
- Compact Air Purifier (`HOME-305`)

### Primary Condition Class Distribution
| Condition | Target Count | Share | Visual Markers Programmed |
| :--- | :--- | :--- | :--- |
| **`NEW`** | 36 | 30% | Crisp rectangular carton, 100% intact green factory tamper sticker across lid seam. |
| **`OPEN_BOX`** | 48 | 40% | Tamper sticker severed (`BROKEN`), stripped (`MISSING`), or resealed (`RESEALED`) with ajar carton flap. |
| **`DAMAGED`** | 36 | 30% | Carton corner compression (`CRUSHED_BOX`), carton laceration (`TEAR_PUNCTURE`), moisture stain (`LIQUID_STAIN`), or product surface fissure (`ITEM_DEFECT`). |

---

## 3. Gold Standard Quality Benchmark

From the total corpus, **30 items (25%)** are designated as verified **Gold Standard Benchmark Records** stored in `data/gold/gold_annotations.json`.

### Purpose
In human annotation operations, a blinded "Gold Set" (or "honeypot") serves as the objective ground truth against which annotator performance is continually monitored for:
- Accuracy against consensus ground truth
- Primary condition error rates
- Cohen's Kappa ($\kappa$) inter-rater agreement against verified labels
- Confusion matrices to identify systematic misinterpretations (e.g., confusing `OPEN_BOX` with minor cosmetic `DAMAGED`)

### Difficulty Stratification
- **EASY**: High-contrast, unambiguous cues (e.g., huge puncture hole or pristine sealed green sticker).
- **MEDIUM**: Standard operational returns (e.g., severed tape flap, moderate corner buckling).
- **HARD**: Borderline edge cases designed to test SOP adherence (e.g., slight lid lift vs. resealed tape).

---

## 4. Dataset-Agnostic Architecture: How to Plug in Real Data

The entire pipeline (`pipeline/ingest.py`, `pipeline/validate.py`, `pipeline/database.py`, and `app/annotation/`) is completely decoupled from how images are produced.

To substitute a real-world product image dataset:
1. Place the new images into `data/images/`.
2. Update or regenerate `data/manifest_tasks.json` with the following simple JSON array:
   ```json
   [
     {
       "task_id": "TSK-0001",
       "image_id": "real_image_0001.jpg",
       "image_path": "data/images/real_image_0001.jpg",
       "product_category": "Electronics",
       "sku": "REAL-SKU-99",
       "synthetic": false
     }
   ]
   ```
3. Update `data/gold/gold_annotations.json` with verified human expert labels for the gold tasks.
4. Run `python scripts/run_pipeline.py`. Zero pipeline code modifications are required.
