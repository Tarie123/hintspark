-- HintSpark learning metrics. Replace PROJECT with your project id.
-- Use these as Looker Studio data sources for the team dashboard.

-- 1. Is learning happening? Time from first run to first pass, per exercise.
WITH firsts AS (
  SELECT session_id, exercise_id,
         MIN(IF(event_type = 'run', ts, NULL)) AS first_run,
         MIN(IF(event_type = 'run' AND passed, ts, NULL)) AS first_pass
  FROM `PROJECT.hintspark.events`
  GROUP BY 1, 2
)
SELECT exercise_id,
       COUNT(*) AS learners,
       COUNTIF(first_pass IS NOT NULL) AS solved,
       ROUND(100 * COUNTIF(first_pass IS NOT NULL) / COUNT(*), 1) AS solve_rate_pct,
       APPROX_QUANTILES(TIMESTAMP_DIFF(first_pass, first_run, SECOND), 2)[OFFSET(1)] AS median_secs_to_fix
FROM firsts
GROUP BY exercise_id
ORDER BY exercise_id;

-- 2. Attempts and hints needed before the first pass.
WITH ordered AS (
  SELECT *, LOGICAL_OR(event_type = 'run' AND passed) OVER (
           PARTITION BY session_id, exercise_id ORDER BY ts
           ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS solved_before
  FROM `PROJECT.hintspark.events`
)
SELECT exercise_id,
       ROUND(AVG(runs), 2) AS avg_runs_before_pass,
       ROUND(AVG(hints), 2) AS avg_hints_before_pass
FROM (
  SELECT session_id, exercise_id,
         COUNTIF(event_type = 'run') AS runs,
         COUNTIF(event_type = 'explain') AS hints
  FROM ordered
  WHERE solved_before IS NOT TRUE
  GROUP BY 1, 2
)
GROUP BY exercise_id
ORDER BY exercise_id;

-- 3. The "about to quit" signal: learners who failed 3+ times and never passed.
SELECT exercise_id,
       COUNT(*) AS stuck_learners
FROM (
  SELECT session_id, exercise_id,
         COUNTIF(event_type = 'run' AND NOT passed) AS fails,
         COUNTIF(event_type = 'run' AND passed) AS passes
  FROM `PROJECT.hintspark.events`
  GROUP BY 1, 2
)
WHERE fails >= 3 AND passes = 0
GROUP BY exercise_id
ORDER BY stuck_learners DESC;

-- 4. Do the trace features help? Pass rate after using "jump to divergence" vs not.
WITH s AS (
  SELECT session_id, exercise_id,
         LOGICAL_OR(event_type = 'jump_to_divergence') AS used_jump,
         LOGICAL_OR(event_type = 'run' AND passed) AS solved
  FROM `PROJECT.hintspark.events`
  GROUP BY 1, 2
)
SELECT used_jump, COUNT(*) AS learners, ROUND(100 * COUNTIF(solved) / COUNT(*), 1) AS solve_rate_pct
FROM s GROUP BY used_jump;

-- 5. AI explanation health: how often NVIDIA answered vs fallback was used.
SELECT source, COUNT(*) AS explanations
FROM `PROJECT.hintspark.events`
WHERE event_type = 'explain'
GROUP BY source;

-- 6. Exercise abandonment rate (started or ran, never passed)
WITH attempts AS (
  SELECT
    exercise_id,
    session_id,
    MAX(IF(event_type = 'run' AND passed, 1, 0)) AS completed
  FROM hintspark.events
  GROUP BY exercise_id, session_id
)
SELECT
  exercise_id,
  COUNT(*) AS total_sessions,
  COUNTIF(completed = 0) AS abandoned_sessions,
  ROUND(100.0 * COUNTIF(completed = 0) / COUNT(*), 1) AS abandonment_rate_pct
FROM attempts
GROUP BY exercise_id
ORDER BY abandonment_rate_pct DESC;
