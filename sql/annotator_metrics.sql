-- ============================================================================
-- ANNOTATIONOPS: ANNOTATOR WORKFORCE PERFORMANCE ANALYTICS
-- Purpose: Monitor individual and team productivity, accuracy against gold benchmark,
--          rejection rates, rework rates, and operational shifts.
-- Queries: 11 through 15
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Complete Annotator Scorecard (Productivity, Speed, Quality, Rejections)
-- Covers: Query 11 (Annotator Productivity), Query 12 (Annotator Quality),
--         Query 13 (Gold Accuracy by Annotator)
-- ----------------------------------------------------------------------------
WITH valid_kpis AS (
    SELECT 
        annotator_id,
        COUNT(*) AS total_completed,
        ROUND(AVG(processing_time_seconds), 2) AS avg_cycle_time_sec,
        SUM(is_rework) AS rework_count,
        SUM(is_escalated) AS escalation_count,
        SUM(CASE WHEN anomaly_flag IS NOT NULL THEN 1 ELSE 0 END) AS speed_anomalies
    FROM annotations
    GROUP BY annotator_id
),
gold_eval AS (
    SELECT 
        a.annotator_id,
        COUNT(*) AS gold_tasks_reviewed,
        SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) AS gold_correct
    FROM annotations a
    JOIN gold_annotations g ON a.task_id = g.task_id
    GROUP BY a.annotator_id
),
rejections AS (
    SELECT 
        annotator_id,
        COUNT(*) AS rejections_blocked
    FROM rejection_audit
    WHERE annotator_id IS NOT NULL
    GROUP BY annotator_id
)
SELECT 
    ann.annotator_id,
    ann.display_name,
    ann.role,
    ann.team,
    ann.shift,
    ann.experience_level,
    COALESCE(v.total_completed, 0) AS tasks_completed,
    COALESCE(v.avg_cycle_time_sec, 0.0) AS avg_duration_sec,
    COALESCE(r.rejections_blocked, 0) AS rejections_count,
    ROUND(
        COALESCE(r.rejections_blocked, 0) * 100.0 / 
        NULLIF(COALESCE(v.total_completed, 0) + COALESCE(r.rejections_blocked, 0), 0),
        2
    ) AS rejection_rate_pct,
    COALESCE(v.rework_count, 0) AS rework_count,
    ROUND(
        COALESCE(v.rework_count, 0) * 100.0 / NULLIF(COALESCE(v.total_completed, 0), 0),
        2
    ) AS rework_rate_pct,
    COALESCE(g.gold_tasks_reviewed, 0) AS gold_tasks_evaluated,
    ROUND(
        COALESCE(g.gold_correct, 0) * 100.0 / NULLIF(COALESCE(g.gold_tasks_reviewed, 0), 0),
        2
    ) AS gold_accuracy_pct,
    -- Performance Quadrant Flagging
    CASE 
        WHEN (COALESCE(g.gold_correct, 0) * 100.0 / NULLIF(COALESCE(g.gold_tasks_reviewed, 0), 0)) >= 95.0 
             AND COALESCE(v.total_completed, 0) >= 2000 THEN 'HIGH_PERFORMER'
        WHEN (COALESCE(g.gold_correct, 0) * 100.0 / NULLIF(COALESCE(g.gold_tasks_reviewed, 0), 0)) < 92.0 THEN 'CALIBRATION_PRIORITY'
        ELSE 'STANDARD_COMPLIANT'
    END AS operational_quadrant
FROM annotators ann
LEFT JOIN valid_kpis v ON ann.annotator_id = v.annotator_id
LEFT JOIN gold_eval g ON ann.annotator_id = g.annotator_id
LEFT JOIN rejections r ON ann.annotator_id = r.annotator_id
ORDER BY tasks_completed DESC;

-- ----------------------------------------------------------------------------
-- 2. Team and Operational Shift Performance Comparison
-- Covers: Query 14 (Shift & Team Variance)
-- ----------------------------------------------------------------------------
SELECT 
    ann.team,
    ann.shift,
    COUNT(DISTINCT ann.annotator_id) AS active_annotators,
    COUNT(a.annotation_id) AS total_shift_volume,
    ROUND(AVG(a.processing_time_seconds), 2) AS avg_shift_cycle_time_sec,
    ROUND(
        SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) * 100.0 / 
        NULLIF(COUNT(g.task_id), 0), 
        2
    ) AS shift_gold_accuracy_pct
FROM annotators ann
JOIN annotations a ON ann.annotator_id = a.annotator_id
LEFT JOIN gold_annotations g ON a.task_id = g.task_id
GROUP BY ann.team, ann.shift
ORDER BY ann.team, ann.shift;

-- ----------------------------------------------------------------------------
-- 3. Experience Tier Productivity & Error Rate Distribution
-- Covers: Query 15 (Seniority & Experience Impact)
-- ----------------------------------------------------------------------------
SELECT 
    ann.experience_level,
    COUNT(DISTINCT ann.annotator_id) AS annotator_count,
    COUNT(a.annotation_id) AS annotations_completed,
    ROUND(AVG(a.processing_time_seconds), 2) AS mean_duration_sec,
    ROUND(
        SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) * 100.0 / 
        NULLIF(COUNT(g.task_id), 0),
        2
    ) AS gold_accuracy_pct,
    ROUND(
        100.0 - (SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) * 100.0 / 
        NULLIF(COUNT(g.task_id), 0)),
        2
    ) AS error_rate_pct
FROM annotators ann
JOIN annotations a ON ann.annotator_id = a.annotator_id
LEFT JOIN gold_annotations g ON a.task_id = g.task_id
GROUP BY ann.experience_level
ORDER BY gold_accuracy_pct DESC;
