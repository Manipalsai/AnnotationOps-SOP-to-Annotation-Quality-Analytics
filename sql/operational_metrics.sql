-- ============================================================================
-- ANNOTATIONOPS: OPERATIONAL KPIS & THROUGHPUT ANALYTICS
-- Purpose: Monitor workflow velocity, pending backlog, cycle times, and operational SLA adherence.
-- Queries: 1 through 10
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Total Task Volume, Completed Tasks, Backlog, and Completion Rate
-- Covers: Query 1 (Total Task Volume), Query 2 (Completed Tasks),
--         Query 3 (Backlog), Query 4 (Completion Rate)
-- ----------------------------------------------------------------------------
WITH queue_summary AS (
    SELECT 
        COUNT(*) AS total_tasks,
        SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed_tasks,
        SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending_backlog,
        SUM(CASE WHEN status = 'REWORK' THEN 1 ELSE 0 END) AS rework_tasks,
        SUM(CASE WHEN status = 'ESCALATED' THEN 1 ELSE 0 END) AS escalated_tasks
    FROM tasks
)
SELECT 
    total_tasks,
    completed_tasks,
    pending_backlog,
    rework_tasks,
    escalated_tasks,
    ROUND(completed_tasks * 100.0 / NULLIF(total_tasks, 0), 2) AS completion_rate_pct,
    -- Backlog reconciliation check
    (completed_tasks + pending_backlog + rework_tasks + escalated_tasks = total_tasks) AS is_reconciled
FROM queue_summary;

-- ----------------------------------------------------------------------------
-- 2. Daily Throughput and Cycle Time
-- Covers: Query 5 (Daily Throughput)
-- ----------------------------------------------------------------------------
SELECT 
    SUBSTR(annotation_timestamp, 1, 10) AS operational_date,
    COUNT(*) AS daily_volume_completed,
    ROUND(AVG(processing_time_seconds), 2) AS avg_cycle_time_seconds,
    SUM(is_rework) AS rework_events,
    SUM(is_escalated) AS escalation_events
FROM annotations
GROUP BY SUBSTR(annotation_timestamp, 1, 10)
ORDER BY operational_date ASC;

-- ----------------------------------------------------------------------------
-- 3. Weekly Throughput Velocity
-- Covers: Query 6 (Weekly Throughput)
-- ----------------------------------------------------------------------------
SELECT 
    CAST(((STRFTIME('%s', annotation_timestamp) - STRFTIME('%s', '2026-07-06 08:00:00')) / (7 * 86400)) + 1 AS INT) AS week_number,
    COUNT(*) AS weekly_throughput_volume,
    COUNT(DISTINCT task_id) AS distinct_tasks_completed,
    ROUND(AVG(processing_time_seconds), 2) AS avg_cycle_time_seconds,
    ROUND(COUNT(*) * 1.0 / 7, 1) AS avg_daily_rate_this_week
FROM annotations
GROUP BY week_number
ORDER BY week_number ASC;

-- ----------------------------------------------------------------------------
-- 4. Average and Median Cycle Time
-- Covers: Query 7 (Average Cycle Time), Query 8 (Median Cycle Time)
-- ----------------------------------------------------------------------------
WITH ordered_durations AS (
    SELECT 
        processing_time_seconds,
        ROW_NUMBER() OVER (ORDER BY processing_time_seconds) AS row_num,
        COUNT(*) OVER () AS total_count
    FROM annotations
)
SELECT 
    ROUND((SELECT AVG(processing_time_seconds) FROM annotations), 2) AS avg_cycle_time_sec,
    ROUND(AVG(processing_time_seconds), 2) AS median_cycle_time_sec
FROM ordered_durations
WHERE row_num IN ((total_count + 1) / 2, (total_count + 2) / 2);

-- ----------------------------------------------------------------------------
-- 5. Overall Pipeline Rejection Rate
-- Covers: Query 9 (Rejection Rate)
-- Target SLA: < 3.0%
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
    ) AS pipeline_rejection_rate_pct,
    -- Simulated Target SLA Comparison
    3.0 AS target_max_rejection_rate_pct,
    CASE 
        WHEN (total_rejected_submissions * 100.0 / NULLIF(total_valid_submissions + total_rejected_submissions, 0)) <= 3.0 
        THEN 'SLA MET' 
        ELSE 'SLA BREACH' 
    END AS rejection_sla_status
FROM totals;

-- ----------------------------------------------------------------------------
-- 6. Rework and Escalation Operational Volume
-- Covers: Query 10 (Rework Rate)
-- ----------------------------------------------------------------------------
SELECT 
    COUNT(*) AS total_completed_tasks,
    SUM(CASE WHEN status = 'REWORK' THEN 1 ELSE 0 END) AS rework_tasks,
    SUM(CASE WHEN status = 'ESCALATED' THEN 1 ELSE 0 END) AS escalated_tasks,
    ROUND(
        SUM(CASE WHEN status = 'REWORK' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS rework_rate_pct,
    ROUND(
        SUM(CASE WHEN status = 'ESCALATED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS escalation_rate_pct
FROM tasks
WHERE status != 'PENDING';
