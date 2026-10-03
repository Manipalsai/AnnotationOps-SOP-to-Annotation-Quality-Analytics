-- ============================================================================
-- ANNOTATIONOPS: DATA QUALITY AUDIT & REJECTION ANALYTICS
-- Purpose: Audit pipeline integrity, identify duplicate submissions, null anomalies,
--          and conditional business rule violations caught by the ingestion firewall.
-- Queries: 23 through 25
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Duplicate Submission Detection Audit
-- Covers: Query 23 (Duplicate Detection)
-- Identifies any duplicate attempts in rejection audit or annotations table.
-- ----------------------------------------------------------------------------
SELECT 
    task_id,
    annotator_id,
    COUNT(*) AS attempts_count,
    rejection_code,
    MIN(rejected_at) AS first_attempt_at,
    MAX(rejected_at) AS latest_attempt_at
FROM rejection_audit
WHERE rejection_code = 'ERR_DUPLICATE_SUBMISSION'
GROUP BY task_id, annotator_id
ORDER BY attempts_count DESC;

-- ----------------------------------------------------------------------------
-- 2. Completeness and Missing Values Audit on Validated Corpus
-- Covers: Query 24 (Missing Values)
-- Validates zero unexpected nulls in core identifier and condition columns.
-- ----------------------------------------------------------------------------
SELECT 
    COUNT(*) AS total_records_audited,
    SUM(CASE WHEN task_id IS NULL OR TRIM(task_id) = '' THEN 1 ELSE 0 END) AS missing_task_id,
    SUM(CASE WHEN annotator_id IS NULL OR TRIM(annotator_id) = '' THEN 1 ELSE 0 END) AS missing_annotator_id,
    SUM(CASE WHEN condition IS NULL THEN 1 ELSE 0 END) AS missing_condition,
    SUM(CASE WHEN annotation_timestamp IS NULL THEN 1 ELSE 0 END) AS missing_timestamp,
    SUM(CASE WHEN processing_time_seconds IS NULL OR processing_time_seconds <= 0 THEN 1 ELSE 0 END) AS invalid_durations,
    -- SOP Conditional Invariants Check on Clean Corpus
    SUM(CASE WHEN condition = 'NEW' AND (damage_type IS NOT NULL OR packaging_condition IS NOT NULL) THEN 1 ELSE 0 END) AS sop_new_violations,
    SUM(CASE WHEN condition = 'OPEN_BOX' AND (packaging_condition IS NULL OR seal_condition IS NULL) THEN 1 ELSE 0 END) AS sop_openbox_violations,
    SUM(CASE WHEN condition = 'DAMAGED' AND (damage_type IS NULL OR damage_severity IS NULL) THEN 1 ELSE 0 END) AS sop_damaged_violations
FROM annotations;

-- ----------------------------------------------------------------------------
-- 3. Rejection Root Causes: Invalid Labels & Conditional Rule Violations
-- Covers: Query 25 (Invalid Labels & Conditional-Rule Violations)
-- Audits rejection sink breakdown by validation stage and error category.
-- ----------------------------------------------------------------------------
SELECT 
    validation_stage,
    rejection_code,
    COUNT(*) AS failure_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM rejection_audit), 2) AS share_of_rejections_pct,
    MIN(rejected_at) AS first_detected,
    MAX(rejected_at) AS last_detected
FROM rejection_audit
GROUP BY validation_stage, rejection_code
ORDER BY failure_count DESC;

-- ----------------------------------------------------------------------------
-- 4. Annotator Rejection Profile (Quality Assurance Root-Cause Analysis)
-- ----------------------------------------------------------------------------
SELECT 
    r.annotator_id,
    ann.display_name,
    ann.role,
    ann.team,
    COUNT(*) AS total_rejections,
    SUM(CASE WHEN r.rejection_code = 'ERR_CONDITIONAL_FIELD_MISSING' THEN 1 ELSE 0 END) AS missing_conditional_fields,
    SUM(CASE WHEN r.rejection_code = 'ERR_UNEXPECTED_FIELD_PRESENT' THEN 1 ELSE 0 END) AS unexpected_secondary_fields,
    SUM(CASE WHEN r.rejection_code = 'ERR_INVALID_LABEL' THEN 1 ELSE 0 END) AS invalid_labels,
    SUM(CASE WHEN r.rejection_code = 'ERR_DESCRIPTION_TOO_SHORT' THEN 1 ELSE 0 END) AS short_descriptions,
    SUM(CASE WHEN r.rejection_code = 'ERR_IMPOSSIBLE_TIME' THEN 1 ELSE 0 END) AS pacing_violations
FROM rejection_audit r
LEFT JOIN annotators ann ON r.annotator_id = ann.annotator_id
GROUP BY r.annotator_id
ORDER BY total_rejections DESC;
