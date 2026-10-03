# Data Dictionary & Schema Reference

**System:** ANNOTATIONOPS  
**Scope:** Raw Payloads, Warehouse Tables, Audit Sinks, and Gold Benchmark Metadata  
**Version:** 1.0.0  

---

## 1. Clean Annotations (`annotations` table & `clean_annotations.jsonl`)

Represents validated, audit-passed human annotation records loaded into the analytics warehouse.

| Field Name | Storage Type | Nullable? | Constraints / Allowed Values | Description & Analytical Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `annotation_id` | `TEXT` (UUID) | No | Primary Key | Globally unique identifier for the verified submission record. |
| `task_id` | `TEXT` | No | Foreign Key -> `tasks(task_id)` | Identifier of the evaluated returned item. |
| `image_id` | `TEXT` | No | Valid image file name | Reference to the visual photographic inspection asset. |
| `annotator_id` | `TEXT` | No | Foreign Key -> `annotators(annotator_id)` | Unique identifier of the human auditor who classified the item. |
| `condition` | `TEXT` (Enum) | No | `NEW`, `OPEN_BOX`, `DAMAGED` | Primary triage classification governed by SOP decision hierarchy. |
| `packaging_condition` | `TEXT` (Enum) | Yes | `INTACT`, `WORN`, `MISSING` | Physical integrity of retail packaging. **Required for `OPEN_BOX`**, forbidden otherwise. |
| `seal_condition` | `TEXT` (Enum) | Yes | `BROKEN`, `MISSING`, `RESEALED` | State of tamper-evident sticker. **Required for `OPEN_BOX`**, forbidden otherwise. |
| `damage_type` | `TEXT` (Enum) | Yes | `CRUSHED_BOX`, `TEAR_PUNCTURE`, `LIQUID_STAIN`, `ITEM_DEFECT` | Structural failure mechanism. **Required for `DAMAGED`**, forbidden otherwise. |
| `damage_severity` | `TEXT` (Enum) | Yes | `MINOR`, `MODERATE`, `SEVERE` | Magnitude of damage. **Required for `DAMAGED`**, forbidden otherwise. |
| `description` | `TEXT` | Yes | 10 to 250 characters | Factual visual defect description. **Required for `DAMAGED`**, forbidden otherwise. |
| `annotation_timestamp` | `TIMESTAMP` | No | ISO-8601 UTC string | Precise timestamp when annotation was completed. Used for time-series throughput. |
| `processing_time_seconds`| `REAL` | No | $0.5 \le t \le 1800.0$ | Active seconds spent on task. Used for cycle time and fatigue tracking. |
| `anomaly_flag` | `TEXT` | Yes | `WARN_SPEED_ANOMALY_FAST`, `null` | Operational review tag if submission completed faster than nominal threshold ($< 2.0\text{s}$). |
| `schema_version` | `TEXT` | No | SemVer (e.g. `1.0.0`) | Version of specification contract against which submission was validated. |
| `ingested_at` | `TIMESTAMP` | No | Default `CURRENT_TIMESTAMP` | System ingestion timestamp for warehouse auditability. |

---

## 2. Rejection Audit Log (`rejection_audit` table & `rejected_annotations.jsonl`)

Captures all submissions blocked by automated validation gates with structured root-cause reason codes.

| Field Name | Storage Type | Nullable? | Example Values | Description & Operational Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `rejection_id` | `INTEGER` | No | Auto-increment Primary Key | Unique identifier for the rejection event. |
| `task_id` | `TEXT` | Yes | `TSK-0008` | Task ID associated with rejected submission (null if schema unparseable). |
| `annotator_id` | `TEXT` | Yes | `ANNO-02` | Submitting auditor (null if missing in payload). Used for annotator error rate tracking. |
| `rejection_code` | `TEXT` | No | `ERR_CONDITIONAL_FIELD_MISSING` | Standardized machine-readable error code (see Controlled Vocabulary below). |
| `rejection_reason` | `TEXT` | No | Human-readable explanation | Detailed error message emitted by Pydantic validation engine. |
| `validation_stage` | `TEXT` | No | `STAGE_1_SCHEMA`, `STAGE_2_CATEGORICAL`, `STAGE_3_CONDITIONAL_RULES`, `STAGE_4_OPERATIONAL` | Pipeline stage where submission was intercepted. |
| `raw_payload` | `TEXT` | No | JSON string | Exact raw payload submitted, preserved for dispute resolution or retraining. |
| `rejected_at` | `TIMESTAMP` | No | ISO-8601 UTC string | Timestamp when rejection was recorded. |

---

## 3. Standardized Rejection Reason Codes

| Rejection Code | Validation Stage | Trigger Condition | Operational Action Required |
| :--- | :--- | :--- | :--- |
| `ERR_MISSING_TASK_ID` | `STAGE_1_SCHEMA` | `task_id` is missing, null, or empty string. | Inspect frontend client session state. |
| `ERR_MISSING_ANNOTATOR_ID`| `STAGE_1_SCHEMA` | `annotator_id` is missing or null. | Prompt auditor to log in / select ID. |
| `ERR_DUPLICATE_SUBMISSION` | `STAGE_1_SCHEMA` | Duplicate `(task_id, annotator_id)` submission in batch. | Block re-submission; verify queue locking. |
| `ERR_SCHEMA_MISMATCH` | `STAGE_1_SCHEMA` | Malformed JSON or unparseable payload structure. | Check API payload serialization. |
| `ERR_INVALID_LABEL` | `STAGE_2_CATEGORICAL` | Primary condition not in `[NEW, OPEN_BOX, DAMAGED]`. | Auditor coaching on allowed condition labels. |
| `ERR_CONDITIONAL_FIELD_MISSING` | `STAGE_3_CONDITIONAL_RULES` | Missing packaging/seal on `OPEN_BOX` or missing damage attributes on `DAMAGED`. | Retrain auditor on SOP conditional matrix. |
| `ERR_UNEXPECTED_FIELD_PRESENT` | `STAGE_3_CONDITIONAL_RULES` | Secondary damage/packaging fields populated for condition `NEW`. | Enforce UI dynamic reset upon category change. |
| `ERR_INVALID_ENUM_VALUE` | `STAGE_3_CONDITIONAL_RULES` | Unknown secondary enum value (e.g. `packaging_condition = "TORN"`). | Update client dropdown options to match YAML contract. |
| `ERR_DESCRIPTION_TOO_SHORT` | `STAGE_3_CONDITIONAL_RULES` | Damage description length $< 10$ characters. | Auditor coaching: require objective defect detail. |
| `ERR_IMPOSSIBLE_TIME` | `STAGE_4_OPERATIONAL` | `processing_time_seconds` $< 0.5\text{s}$ or $> 1800\text{s}$. | Technical check on client timer calculation. |
| `WARN_SPEED_ANOMALY_FAST` | `STAGE_4_OPERATIONAL` | `processing_time_seconds` $< 2.0\text{s}$. | Flagged for supervisor quality review (not rejected). |

---

## 4. Gold Standard Benchmarks (`gold_annotations` table)

Verified ground-truth evaluation items used to measure human classification accuracy and Cohen's Kappa.

| Field Name | Storage Type | Nullable? | Description |
| :--- | :--- | :--- | :--- |
| `task_id` | `TEXT` | No | Primary Key -> `tasks(task_id)`. |
| `image_id` | `TEXT` | No | Visual reference asset. |
| `ground_truth_condition` | `TEXT` (Enum) | No | Verified consensus condition label. |
| `ground_truth_packaging_condition` | `TEXT` (Enum) | Yes | Verified packaging state. |
| `ground_truth_seal_condition` | `TEXT` (Enum) | Yes | Verified tamper seal state. |
| `ground_truth_damage_type` | `TEXT` (Enum) | Yes | Verified damage mechanism. |
| `ground_truth_damage_severity` | `TEXT` (Enum) | Yes | Verified damage severity tier. |
| `ground_truth_description` | `TEXT` | Yes | Verified expert damage summary. |
| `difficulty` | `TEXT` (Enum) | No | `EASY`, `MEDIUM`, `HARD` stratification. |
| `verified_by` | `TEXT` | No | Name / Role of quality specialist who established benchmark. |
| `synthetic` | `INTEGER` | No | Flag (`1` = synthetic fixture, `0` = real return). |

---

## 5. Tasks Queue (`tasks` table)

| Field Name | Storage Type | Nullable? | Description |
| :--- | :--- | :--- | :--- |
| `task_id` | `TEXT` | No | Unique identifier for returned product unit (`TSK-0001`). |
| `image_id` | `TEXT` | No | Filename of inspection photograph (`img_0001.png`). |
| `image_path` | `TEXT` | No | Local relative storage path (`data/images/img_0001.png`). |
| `product_category` | `TEXT` | Yes | E-commerce retail merchandise category. |
| `sku` | `TEXT` | Yes | Stock Keeping Unit code (`AUDIO-880`). |
| `synthetic` | `INTEGER` | No | Explicit synthetic data indicator. |
| `created_at` | `TIMESTAMP` | No | Timestamp of task queue ingestion. |

---

## 6. Workforce Roster (`annotators` table)

| Field Name | Storage Type | Nullable? | Description |
| :--- | :--- | :--- | :--- |
| `annotator_id` | `TEXT` | No | Primary Key (`ANNO-01`). |
| `display_name` | `TEXT` | No | Auditor full name or callsign. |
| `role` | `TEXT` | No | Operational role (`Junior Annotator`, `Standard Annotator`, `Senior Annotator`, `Lead Specialist`). |
| `active` | `INTEGER` | No | `1` if currently active in workforce pool. |
