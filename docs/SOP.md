# Standard Operating Procedure (SOP): Returned Product Condition Classification

**Document ID:** SOP-OPS-2026-001  
**Version:** 1.0.0  
**Effective Date:** 2026-10-01  
**Target Role:** Science Annotation Operations Analyst & Quality Evaluator  
**Task Name:** `returned_product_condition`  
**Status:** Approved for Production  

---

## 1. Purpose
This Standard Operating Procedure (SOP) governs the human annotation and audit workflow for grading the physical condition of returned e-commerce customer items. High-accuracy condition labels are critical for downstream reverse-logistics routing (restock as new, discount resale, liquidation, or hazardous disposal) and for training automated vision-inspection models.

---

## 2. Scope
This protocol applies to all human annotators, quality audit analysts, and automated validation systems assessing return-dock imagery across apparel, electronics, consumables, and home goods.

---

## 3. Definitions
- **Item**: The primary retail merchandise contained in the return.
- **Retail Packaging**: The original branded carton, blister pack, or shrink-wrap.
- **Transit Outer Box**: The generic brown shipping box or poly-mailer used for delivery (distinguished from retail packaging).
- **Factory Seal**: Tamper-evident adhesive sticker, branded tape, pull-tab, or vacuum shrink-wrap applied at manufacture.
- **Cosmetic Blemish**: Surface marks, superficial dust, or minor scuffs that do not affect structural integrity or resale presentation.
- **Structural Defect**: Creases, tears, punctures, crushed corners, water staining, or broken closures.

---

## 4. Primary Condition Categories & Core Decision Hierarchy

Every return unit must be classified into exactly one primary condition category according to this strict hierarchical precedence:

```
[Is there functional or physical structural damage to item or retail box?]
    ├── YES ────────────────────────► DAMAGED (Priority 1)
    └── NO
         ├── [Is factory seal broken or packaging opened/missing?]
         │        ├── YES ──────────► OPEN_BOX (Priority 2)
         │        └── NO
         │             └── [Is factory seal fully intact and packaging pristine?]
         │                      └──► NEW (Priority 3)
```

### 4.1 Condition: `NEW`
- **Definition**: The item is completely unopened, retains 100% intact manufacturer seal/shrink-wrap, and the retail packaging has zero structural defects.
- **Allowed packaging defects**: None beyond negligible handling scuffs (< 5mm).
- **Conditional Field Rule**: No secondary condition or damage fields may be populated.

### 4.2 Condition: `OPEN_BOX`
- **Definition**: The item is physically undamaged and complete, but the manufacturer seal is broken, packaging has been unsealed, or outer retail packaging is opened.
- **Conditional Field Rule**: Annotators **must** record both `packaging_condition` and `seal_condition`. Damage fields must **not** be populated.

### 4.3 Condition: `DAMAGED`
- **Definition**: The item or its primary retail packaging exhibits visible structural damage, tearing, crushing, liquid exposure, or puncture.
- **Conditional Field Rule**: Annotators **must** record `damage_type`, `damage_severity`, and `description`. Open box packaging fields must **not** be populated.

---

## 5. Controlled Vocabulary & Allowed Attributes

### 5.1 Secondary Attributes for `OPEN_BOX`
| Attribute | Allowed Values | Definition / Decision Rule |
| :--- | :--- | :--- |
| `packaging_condition` | `INTACT` | Retail box present, clean, opened neatly without rips. |
| | `WORN` | Box has visible creases, fraying, tape residue, or shelf wear. |
| | `MISSING` | Retail packaging completely absent (loose in polybag). |
| `seal_condition` | `BROKEN` | Adhesive seal cut, torn, or lifted. |
| | `MISSING` | Seal tape stripped away or unsealed flap opened. |
| | `RESEALED` | Non-OEM clear tape or tape over tape applied. |

### 5.2 Secondary Attributes for `DAMAGED`
| Attribute | Allowed Values | Definition / Decision Rule |
| :--- | :--- | :--- |
| `damage_type` | `CRUSHED_BOX` | Carton corner collapse, buckling, or compression > 10% volume. |
| | `TEAR_PUNCTURE` | Penetration through retail carton or laceration > 15mm. |
| | `LIQUID_STAIN` | Moisture discoloration, water damage, or oil saturation. |
| | `ITEM_DEFECT` | Visible crack, dent, chip, or scratch on the actual merchandise. |
| `damage_severity` | `MINOR` | Cosmetic flaw only; internal contents completely protected. |
| | `MODERATE` | Box structural integrity compromised or product superficially dented. |
| | `SEVERE` | Crushed through to interior, liquid soaked, or shattered item. |
| `description` | Text (10–250 chars) | Factual, objective summary (e.g., "Left bottom corner crushed inward 3cm"). |

---

## 6. Conditional Logic Matrix (Automated Contract)

| Primary Condition | `packaging_condition` | `seal_condition` | `damage_type` | `damage_severity` | `description` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`NEW`** | ❌ FORBIDDEN | ❌ FORBIDDEN | ❌ FORBIDDEN | ❌ FORBIDDEN | ❌ FORBIDDEN |
| **`OPEN_BOX`** | ✅ **REQUIRED** | ✅ **REQUIRED** | ❌ FORBIDDEN | ❌ FORBIDDEN | ❌ FORBIDDEN |
| **`DAMAGED`** | ❌ FORBIDDEN | ❌ FORBIDDEN | ✅ **REQUIRED** | ✅ **REQUIRED** | ✅ **REQUIRED** |

*Rule Violation Handling:* Any record violating this matrix is considered a critical schema failure and will be rejected at ingestion with error code `ERR_CONDITIONAL_FIELD_VIOLATION`.

---

## 7. Concrete Examples & Borderline Cases

| Case # | Visual Description | Correct Label | Secondary Fields | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **EX-01** | Electronics box in factory shrink-wrap, perfectly square, no marks. | `NEW` | None | Fully factory-sealed, retail-ready. |
| **EX-02** | Blender box with circular clear sticker sliced cleanly, box flaps closed, no dents. | `OPEN_BOX` | `packaging_condition: INTACT`<br>`seal_condition: BROKEN` | Seal is severed, but packaging has zero structural defects. |
| **EX-03** | Shoe box with corner ripped 2 inches along edge; shoes untouched. | `DAMAGED` | `damage_type: TEAR_PUNCTURE`<br>`damage_severity: MINOR`<br>`description: "2-inch tear along upper right box corner"` | Structural damage to packaging takes precedence over open-box classification. |
| **EX-04** | Headphones with intact seal, but warehouse shipping box arrived soaked in water penetrating retail carton. | `DAMAGED` | `damage_type: LIQUID_STAIN`<br>`damage_severity: MODERATE`<br>`description: "Liquid saturation on retail front panel"` | Liquid contamination breaches retail packaging integrity. |
| **EX-05** | Apparel item in plain clear polybag without original branded box or tags. | `OPEN_BOX` | `packaging_condition: MISSING`<br>`seal_condition: MISSING` | Missing retail presentation, but clothing itself has no tears or stains. |

---

## 8. Quality Expectations & Benchmarks

1. **Target Accuracy (vs. Gold Standard)**: $\ge 95.0\%$
2. **Inter-Annotator Agreement (Cohen's Kappa $\kappa$)**: $\ge 0.85$ (Strong Agreement)
3. **Rejection Rate Target**: $< 2.0\%$ of total submissions.
4. **Pacing / Cycle Time Standard**:
   - Minimum Expected Processing Time: $3.0\text{ seconds}$ (submissions below $2.0\text{s}$ are flagged for anomaly review).
   - Nominal Processing Time: $8.0 - 25.0\text{ seconds}$ per item.
   - Timeout Threshold: $> 300\text{ seconds}$ triggers operational idle flag.

---

## 9. Escalation & Edge-Case Procedures

If an item presents any of the following triggers, annotators must **not** force-fit a label. The item must be flagged as `ESCALATE` in the interface:
1. **Biohazard or Chemical Leakage**: Liquid with strong odor, mold, powder, or battery leakage.
2. **Suspected Counterfeit / Tampered Serial**: Barcode scratched off or serial mismatch between box and unit.
3. **Unusable Image**: Blurry, overexposed, occluded barcode, or completely dark image capture.
