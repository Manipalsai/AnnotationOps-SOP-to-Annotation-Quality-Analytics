-- ============================================================================
-- ANNOTATIONOPS: DATA QUALITY & INTEGRITY CHECKS
-- Purpose: Verify warehouse data integrity, detect anomalies, and audit rejections.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Check for Duplicate Annotations (Task ID + Annotator ID collision)
-- Expected Result: 0 rows. Every task should have at most 1 submission per annotator.
-- ----------------------------------------------------------------------------
SELECT 
    task_id,
    annotator_id,
    COUNT(*) AS submission_count
FROM annotations
GROUP BY task_id, annotator_id
HAVING COUNT(*) > 1;

-- ----------------------------------------------------------------------------
-- 2. Check for Missing or Null Critical Identifiers
-- Expected Result: 0 rows. task_id, annotator_id, condition, and timestamp must never be null.
-- ----------------------------------------------------------------------------
SELECT 
    annotation_id,
    task_id,
    annotator_id,
    condition,
    annotation_timestamp
FROM annotations
WHERE task_id IS NULL 
   OR annotator_id IS NULL 
   OR condition IS NULL 
   OR annotation_timestamp IS NULL;

-- ----------------------------------------------------------------------------
-- 3. Check for Unauthorized Primary Condition Labels
-- Expected Result: 0 rows. Only NEW, OPEN_BOX, DAMAGED are permitted.
-- ----------------------------------------------------------------------------
SELECT 
    annotation_id,
    task_id,
    condition
FROM annotations
WHERE condition NOT IN ('NEW', 'OPEN_BOX', 'DAMAGED');

-- ----------------------------------------------------------------------------
-- 4. Check for SOP Conditional Logic Inconsistencies in Warehouse
-- Expected Result: 0 rows.
-- Rule A: NEW must not have secondary fields populated.
-- Rule B: OPEN_BOX must have packaging and seal populated, damage fields null.
-- Rule C: DAMAGED must have damage fields populated, packaging fields null.
-- ----------------------------------------------------------------------------
SELECT 
    annotation_id,
    task_id,
    condition,
    'VIOLATION_NEW_HAS_SECONDARY' AS violation_type
FROM annotations
WHERE condition = 'NEW' 
  AND (packaging_condition IS NOT NULL 
       OR seal_condition IS NOT NULL 
       OR damage_type IS NOT NULL 
       OR damage_severity IS NOT NULL)

UNION ALL

SELECT 
    annotation_id,
    task_id,
    condition,
    'VIOLATION_OPEN_BOX_INVALID' AS violation_type
FROM annotations
WHERE condition = 'OPEN_BOX' 
  AND (packaging_condition IS NULL 
       OR seal_condition IS NULL 
       OR damage_type IS NOT NULL 
       OR damage_severity IS NOT NULL)

UNION ALL

SELECT 
    annotation_id,
    task_id,
    condition,
    'VIOLATION_DAMAGED_INVALID' AS violation_type
FROM annotations
WHERE condition = 'DAMAGED' 
  AND (damage_type IS NULL 
       OR damage_severity IS NULL 
       OR description IS NULL 
       OR packaging_condition IS NOT NULL 
       OR seal_condition IS NOT NULL);

-- ----------------------------------------------------------------------------
-- 5. Rejection Breakdown by Error Code and Validation Stage
-- Answers: What are the root causes of rejected submissions, and where in the pipeline do they fail?
-- ----------------------------------------------------------------------------
SELECT 
    rejection_code,
    validation_stage,
    COUNT(*) AS rejection_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM rejection_audit), 2) AS pct_of_rejections
FROM rejection_audit
GROUP BY rejection_code, validation_stage
ORDER BY rejection_count DESC;

-- ----------------------------------------------------------------------------
-- 6. Pacing Speed Anomaly Audit
-- Answers: Which submissions completed faster than nominal threshold (<2.0s) or took >300s?
-- ----------------------------------------------------------------------------
SELECT 
    annotation_id,
    task_id,
    annotator_id,
    processing_time_seconds,
    anomaly_flag,
    annotation_timestamp
FROM annotations
WHERE anomaly_flag IS NOT NULL 
   OR processing_time_seconds < 2.0 
   OR processing_time_seconds > 300.0
ORDER BY processing_time_seconds ASC;
