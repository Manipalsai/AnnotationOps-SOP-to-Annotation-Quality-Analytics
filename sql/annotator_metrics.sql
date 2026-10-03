-- ============================================================================
-- ANNOTATIONOPS: ANNOTATOR PERFORMANCE & QUALITY SCIENCE ANALYTICS
-- Purpose: Measure individual annotator productivity, rejection rate, and accuracy against gold standard.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Annotator Productivity and Processing Time Summary
-- Answers: How many tasks has each annotator completed, and what is their average cycle time?
-- ----------------------------------------------------------------------------
SELECT 
    ann.annotator_id,
    ann.display_name,
    ann.role,
    COUNT(a.annotation_id) AS tasks_completed,
    ROUND(AVG(a.processing_time_seconds), 2) AS avg_processing_time_seconds,
    ROUND(MIN(a.processing_time_seconds), 2) AS min_processing_time_seconds,
    ROUND(MAX(a.processing_time_seconds), 2) AS max_processing_time_seconds,
    SUM(CASE WHEN a.anomaly_flag IS NOT NULL THEN 1 ELSE 0 END) AS speed_anomaly_flags
FROM annotators ann
LEFT JOIN annotations a ON ann.annotator_id = a.annotator_id
GROUP BY ann.annotator_id, ann.display_name, ann.role
ORDER BY tasks_completed DESC;

-- ----------------------------------------------------------------------------
-- 2. Annotator Rejection Rate (Data Quality Screening)
-- Answers: Which annotators have high submission rejection rates at upstream validation gates?
-- ----------------------------------------------------------------------------
WITH valid_counts AS (
    SELECT annotator_id, COUNT(*) AS valid_count
    FROM annotations
    GROUP BY annotator_id
),
rejected_counts AS (
    SELECT annotator_id, COUNT(*) AS rejected_count
    FROM rejection_audit
    WHERE annotator_id IS NOT NULL
    GROUP BY annotator_id
)
SELECT 
    ann.annotator_id,
    ann.display_name,
    COALESCE(vc.valid_count, 0) AS valid_submissions,
    COALESCE(rc.rejected_count, 0) AS rejected_submissions,
    (COALESCE(vc.valid_count, 0) + COALESCE(rc.rejected_count, 0)) AS total_submissions_attempted,
    ROUND(
        COALESCE(rc.rejected_count, 0) * 100.0 / 
        NULLIF(COALESCE(vc.valid_count, 0) + COALESCE(rc.rejected_count, 0), 0),
        2
    ) AS annotator_rejection_rate_pct
FROM annotators ann
LEFT JOIN valid_counts vc ON ann.annotator_id = vc.annotator_id
LEFT JOIN rejected_counts rc ON ann.annotator_id = rc.annotator_id
ORDER BY annotator_rejection_rate_pct DESC;

-- ----------------------------------------------------------------------------
-- 3. Annotator Accuracy on Blind Gold Benchmark Set
-- Answers: For tasks where an authoritative gold ground-truth label exists,
--          what is each annotator's classification accuracy and error rate?
-- Target: >= 95.0% Accuracy
-- ----------------------------------------------------------------------------
SELECT 
    a.annotator_id,
    ann.display_name,
    COUNT(*) AS gold_tasks_evaluated,
    SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) AS correct_primary_labels,
    SUM(CASE WHEN a.condition != g.ground_truth_condition THEN 1 ELSE 0 END) AS primary_label_errors,
    ROUND(
        SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS gold_accuracy_pct,
    ROUND(
        SUM(CASE WHEN a.condition != g.ground_truth_condition THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS error_rate_pct,
    CASE 
        WHEN (SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) * 1.0 / COUNT(*)) >= 0.95 
        THEN 'BENCHMARK_EXCEEDED'
        WHEN (SUM(CASE WHEN a.condition = g.ground_truth_condition THEN 1 ELSE 0 END) * 1.0 / COUNT(*)) >= 0.85 
        THEN 'MEETS_ACCEPTABLE'
        ELSE 'COACHING_REQUIRED'
    END AS operational_quality_tier
FROM annotations a
JOIN gold_annotations g ON a.task_id = g.task_id
JOIN annotators ann ON a.annotator_id = ann.annotator_id
GROUP BY a.annotator_id, ann.display_name
ORDER BY gold_accuracy_pct DESC;

-- ----------------------------------------------------------------------------
-- 4. Gold Error Breakdown by Condition Category
-- Answers: Which conditions are most frequently confused or mislabeled against gold standards?
-- ----------------------------------------------------------------------------
SELECT 
    g.ground_truth_condition AS true_condition,
    a.condition AS annotated_condition,
    COUNT(*) AS pair_frequency,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM annotations a2 JOIN gold_annotations g2 ON a2.task_id = g2.task_id), 2) AS share_of_gold_evaluations
FROM annotations a
JOIN gold_annotations g ON a.task_id = g.task_id
GROUP BY g.ground_truth_condition, a.condition
ORDER BY pair_frequency DESC;
