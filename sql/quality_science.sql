-- ============================================================================
-- ANNOTATIONOPS: QUALITY SCIENCE & AGREEMENT ANALYTICS
-- Purpose: Evaluate statistical agreement, ground-truth error matrices,
--          difficulty tier degradation, and longitudinal quality drift.
-- Queries: 16 through 22
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Primary Condition Distribution in Validated Corpus
-- Covers: Query 16 (Condition Distribution)
-- ----------------------------------------------------------------------------
SELECT 
    condition,
    COUNT(*) AS total_volume,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM annotations), 2) AS share_pct,
    ROUND(AVG(processing_time_seconds), 2) AS avg_duration_sec
FROM annotations
GROUP BY condition
ORDER BY total_volume DESC;

-- ----------------------------------------------------------------------------
-- 2. Task Difficulty Tier Distribution
-- Covers: Query 17 (Difficulty Distribution)
-- ----------------------------------------------------------------------------
SELECT 
    t.difficulty,
    COUNT(DISTINCT t.task_id) AS distinct_assets,
    COUNT(a.annotation_id) AS total_annotations_completed,
    ROUND(AVG(a.processing_time_seconds), 2) AS avg_cycle_time_seconds
FROM tasks t
LEFT JOIN annotations a ON t.task_id = a.task_id
GROUP BY t.difficulty
ORDER BY 
    CASE t.difficulty 
        WHEN 'EASY' THEN 1 
        WHEN 'MEDIUM' THEN 2 
        WHEN 'HARD' THEN 3 
        ELSE 4 
    END;

-- ----------------------------------------------------------------------------
-- 3. Quality and Accuracy by Difficulty Tier
-- Covers: Query 18 (Quality by Difficulty)
-- Demonstrates: Analytical correlation where harder tasks degrade accuracy.
-- ----------------------------------------------------------------------------
SELECT 
    g.difficulty,
    COUNT(*) AS gold_evaluations_count,
    SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) AS correct_evaluations,
    ROUND(
        SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS accuracy_pct,
    ROUND(
        100.0 - (SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) * 100.0 / COUNT(*)),
        2
    ) AS error_rate_pct,
    ROUND(AVG(a.processing_time_seconds), 2) AS avg_processing_time_sec
FROM annotations a
JOIN gold_annotations g ON a.task_id = g.task_id
GROUP BY g.difficulty
ORDER BY accuracy_pct DESC;

-- ----------------------------------------------------------------------------
-- 4. Confusion Matrix and Error Distribution
-- Covers: Query 19 (Error Distribution / Confusion Matrix)
-- ----------------------------------------------------------------------------
SELECT 
    g.ground_truth_condition AS actual_condition,
    a.condition AS predicted_condition,
    COUNT(*) AS classification_count,
    CASE WHEN g.ground_truth_condition = a.condition THEN 'CORRECT' ELSE 'ERROR' END AS classification_result
FROM annotations a
JOIN gold_annotations g ON a.task_id = g.task_id
GROUP BY g.ground_truth_condition, a.condition
ORDER BY g.ground_truth_condition, classification_count DESC;

-- ----------------------------------------------------------------------------
-- 5. Inter-Annotator Agreement (Multi-Rater Concordance)
-- Covers: Query 20 (Agreement Rate)
-- ----------------------------------------------------------------------------
WITH multi_rater_tasks AS (
    SELECT 
        task_id,
        COUNT(DISTINCT annotator_id) AS raters_count,
        COUNT(DISTINCT condition) AS distinct_conditions_assigned
    FROM annotations
    GROUP BY task_id
    HAVING COUNT(DISTINCT annotator_id) >= 2
)
SELECT 
    COUNT(*) AS total_multi_rated_tasks,
    SUM(CASE WHEN distinct_conditions_assigned = 1 THEN 1 ELSE 0 END) AS unanimous_agreement_tasks,
    ROUND(
        SUM(CASE WHEN distinct_conditions_assigned = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS raw_concordance_agreement_rate_pct
FROM multi_rater_tasks;

-- ----------------------------------------------------------------------------
-- 6. Weekly Quality Drift Over 12 Operational Weeks
-- Covers: Query 21 (Quality Over Time)
-- Demonstrates: Operational scenario detection (e.g. Week 7 quality dip, Week 10 recovery).
-- ----------------------------------------------------------------------------
SELECT 
    CAST(((STRFTIME('%s', a.annotation_timestamp) - STRFTIME('%s', '2026-07-06 08:00:00')) / (7 * 86400)) + 1 AS INT) AS week_number,
    COUNT(g.task_id) AS gold_evaluations,
    ROUND(
        SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) * 100.0 / COUNT(g.task_id),
        2
    ) AS weekly_accuracy_pct,
    ROUND(
        100.0 - (SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) * 100.0 / COUNT(g.task_id)),
        2
    ) AS weekly_error_rate_pct
FROM annotations a
JOIN gold_annotations g ON a.task_id = g.task_id
GROUP BY week_number
ORDER BY week_number ASC;

-- ----------------------------------------------------------------------------
-- 7. Processing Time Drift Over 12 Operational Weeks
-- Covers: Query 22 (Processing Time Over Time)
-- Demonstrates: Operational scenario detection (e.g. Week 9 inspection protocol surge).
-- ----------------------------------------------------------------------------
SELECT 
    CAST(((STRFTIME('%s', annotation_timestamp) - STRFTIME('%s', '2026-07-06 08:00:00')) / (7 * 86400)) + 1 AS INT) AS week_number,
    COUNT(*) AS total_volume_measured,
    ROUND(AVG(processing_time_seconds), 2) AS avg_duration_seconds,
    ROUND(MIN(processing_time_seconds), 2) AS min_duration_seconds,
    ROUND(MAX(processing_time_seconds), 2) AS max_duration_seconds
FROM annotations
GROUP BY week_number
ORDER BY week_number ASC;
