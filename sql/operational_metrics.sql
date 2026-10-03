-- ============================================================================
-- ANNOTATIONOPS: OPERATIONAL KPIS & THROUGHPUT ANALYTICS
-- Purpose: Monitor workflow velocity, pending backlog, cycle times, and operational SLA adherence.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. High-Level Operations Overview (Queue, Completed, Backlog, Completion Rate)
-- Answers: What is the current operational status of the total task queue?
-- ----------------------------------------------------------------------------
WITH queue_stats AS (
    SELECT COUNT(*) AS total_tasks FROM tasks
),
completed_stats AS (
    SELECT COUNT(DISTINCT task_id) AS completed_tasks FROM annotations
)
SELECT 
    q.total_tasks,
    c.completed_tasks,
    (q.total_tasks - c.completed_tasks) AS pending_backlog,
    ROUND(c.completed_tasks * 100.0 / NULLIF(q.total_tasks, 0), 2) AS completion_rate_pct
FROM queue_stats q
CROSS JOIN completed_stats c;

-- ----------------------------------------------------------------------------
-- 2. Overall Pipeline Rejection Rate
-- Answers: What percentage of total submission volume fails automated validation gates?
-- Target SLA: < 2.0%
-- ----------------------------------------------------------------------------
WITH totals AS (
    SELECT 
        (SELECT COUNT(*) FROM annotations) AS total_valid_submissions,
        (SELECT COUNT(*) FROM rejection_audit) AS total_rejected_submissions
)
SELECT 
    total_valid_submissions,
    total_rejected_submissions,
    (total_valid_submissions + total_rejected_submissions) AS total_submissions_processed,
    ROUND(
        total_rejected_submissions * 100.0 / 
        NULLIF(total_valid_submissions + total_rejected_submissions, 0), 
        2
    ) AS pipeline_rejection_rate_pct
FROM totals;

-- ----------------------------------------------------------------------------
-- 3. Cycle Time / Processing Duration Statistics (Nominal vs. Extreme)
-- Answers: What is the average, minimum, maximum cycle time per task?
-- ----------------------------------------------------------------------------
SELECT 
    COUNT(*) AS total_annotations_measured,
    ROUND(AVG(processing_time_seconds), 2) AS avg_processing_time_seconds,
    ROUND(MIN(processing_time_seconds), 2) AS min_processing_time_seconds,
    ROUND(MAX(processing_time_seconds), 2) AS max_processing_time_seconds
FROM annotations;

-- ----------------------------------------------------------------------------
-- 4. Daily Operational Throughput Trend
-- Answers: How many annotations are completed per day, and what is the day-over-day cycle time?
-- ----------------------------------------------------------------------------
SELECT 
    SUBSTR(annotation_timestamp, 1, 10) AS annotation_date,
    COUNT(DISTINCT task_id) AS unique_tasks_completed,
    COUNT(*) AS total_submissions,
    ROUND(AVG(processing_time_seconds), 2) AS avg_duration_seconds
FROM annotations
GROUP BY SUBSTR(annotation_timestamp, 1, 10)
ORDER BY annotation_date ASC;

-- ----------------------------------------------------------------------------
-- 5. Throughput by Product Category
-- Answers: Which product categories experience higher volume or require longer inspection?
-- ----------------------------------------------------------------------------
SELECT 
    COALESCE(t.product_category, 'Uncategorized') AS product_category,
    COUNT(a.annotation_id) AS total_annotations,
    ROUND(AVG(a.processing_time_seconds), 2) AS avg_duration_seconds,
    SUM(CASE WHEN a.condition = 'DAMAGED' THEN 1 ELSE 0 END) AS damaged_count,
    ROUND(SUM(CASE WHEN a.condition = 'DAMAGED' THEN 1 ELSE 0 END) * 100.0 / COUNT(a.annotation_id), 1) AS damage_rate_pct
FROM annotations a
JOIN tasks t ON a.task_id = t.task_id
GROUP BY t.product_category
ORDER BY total_annotations DESC;
