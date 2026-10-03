# Synthetic Data Generation & Simulation Reference

This document explains the technical architecture, statistical distributions, seeding reproducibility, and scenario models powering the enterprise-scale synthetic workload in AnnotationOps.

> [!IMPORTANT]
> **Dataset Disclosure:** All product assets, metadata, annotator profiles, operational timelines, and submission records are 100% synthetic, generated programmatically using a fixed random seed (`seed = 42`). No real proprietary or customer data is used.

---

## 1. Scale Specifications

| Dimension | Target Specification | Realized Implementation |
| :--- | :--- | :--- |
| **Catalog Assets** | 5,000 unique synthetic products | Exactly 5,000 assets (`AST-00001` to `AST-05000`) |
| **Gold Benchmark Sample** | 5–10% of total workload | 400 assets (8.0% uniform stride coverage) |
| **Annotator Workforce** | 10–20 simulated personas | 12 synthetic annotators (`ANNO-01` to `ANNO-12`) |
| **Operational History** | 8–12 weeks of pacing | 12 full weeks (84 operational days) |
| **Annotation Records** | 20,000–50,000 submission events | 24,983 validated + 893 rejected (~25,876 events) |
| **Representative Images** | Performance-optimized visual assets | 200 distinct PNG renders (600x450, <7MB total disk) |

---

## 2. Statistical Distributions & Controlled Realism

To avoid unconvincing uniform distributions, the generator models realistic industrial operational characteristics:

### 2.1 Product Categories (8 Classes across 2 Groups)
- **Consumer Tech:**
  - `Smart Fitness Watch` (Electronics / Wearables)
  - `Noise-Canceling Headphones` (Audio Products)
  - `Bluetooth Portable Speaker` (Audio Products)
  - `Mechanical Gaming Keyboard` (Computer Accessories)
  - `Ergonomic Wireless Mouse` (Computer Accessories)
- **Household & Appliances:**
  - `Smart Home Security Camera` (Personal Devices)
  - `Compact Espresso Maker` (Small Appliances)
  - `Digital Air Fryer 4QT` (Kitchen Appliances)

### 2.2 Primary Condition & Secondary Attributes
- **Condition Distribution:**
  - `NEW`: 28% of catalog assets
  - `OPEN_BOX`: 42% of catalog assets
  - `DAMAGED`: 30% of catalog assets
- **Task Difficulty Tier:**
  - `EASY`: 40% (clear, obvious condition)
  - `MEDIUM`: 40% (moderate ambiguity)
  - `HARD`: 20% (subtle carton creasing, micro tears, hairline defects)
- **Task Priority Queue:**
  - `NORMAL`: 55%
  - `HIGH`: 25%
  - `LOW`: 10%
  - `CRITICAL`: 10%

---

## 3. Difficulty Correlation Model

Realistic operational correlation is enforced between task difficulty and annotator performance:

- **EASY Tasks:**
  - Processing duration: $-15\%$ faster than baseline.
  - Classification accuracy: $+2.5\%$ higher accuracy.
- **MEDIUM Tasks:**
  - Nominal baseline duration and accuracy.
- **HARD Tasks:**
  - Processing duration: $+30\%$ longer cycle times.
  - Classification accuracy: $-5.0\%$ lower accuracy (increased edge-case confusion).

---

## 4. Controlled 12-Week Operational Scenario Milestones

Rather than unstructured noise, the 84-day operational history simulates 4 distinct operational events:

1. **Week 5: Peak Operational Surge**
   - *Driver:* Catalog expansion simulation.
   - *Impact:* $+40\%$ daily ingestion volume, backlog accumulation, higher pacing variance.
2. **Week 7: Edge-Case Ambiguity Influx**
   - *Driver:* Synthetic batch of high-difficulty packaging edge cases.
   - *Impact:* Temporary $4.5\%$ dip in gold accuracy and increased conditional rule rejections ($6.5\%$ rejection rate).
3. **Week 9: Enhanced Inspection Protocol**
   - *Driver:* Introduction of rigorous defect description guidelines.
   - *Impact:* Average cycle time increased by $28\%$ while annotators adapted to updated criteria.
4. **Week 10: Process Recovery & Stabilization**
   - *Driver:* Calibration workshop and UI prompt optimization.
   - *Impact:* Quality recovered to $>96\%$, and cycle times stabilized within target limits.

---

## 5. Reproducibility & Regeneration

The entire dataset and operational history can be regenerated from scratch deterministically:

```bash
# 1. Regenerate 5,000 product assets and gold baseline
python scripts/generate_dataset.py --num-assets 5000 --seed 42

# 2. Simulate 12-week operational run (25,000 clean annotations)
python scripts/simulate_annotations.py --count 25000 --seed 42

# 3. Reload into SQLite warehouse and reconcile
python -c "from pipeline.database import load_tasks_and_gold, load_processed_and_rejected; load_tasks_and_gold(); load_processed_and_rejected();"
```

Verified by automated tests in `tests/unit/test_dataset_generation.py` and `tests/integration/test_pipeline_performance.py`.
