-- Aggregate-only, read-only. See README.md; use an existing read-only role.
\set ON_ERROR_STOP on
\if :{?report_as_of_utc}
\else
  \echo 'Required: -v report_as_of_utc=2026-11-15T00:00:00Z'
  \quit 2
\endif
\if :{?exclude_user_ids}
\else
  \echo 'Required: -v exclude_user_ids=1,2 (or explicitly empty)'
  \quit 2
\endif
BEGIN TRANSACTION READ ONLY;
SET LOCAL TIME ZONE 'UTC';
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '3s';
WITH params AS (
    SELECT
        (CAST(:'report_as_of_utc' AS timestamptz) AT TIME ZONE 'UTC') - INTERVAL '30 days' AS window_start,
        CAST(:'report_as_of_utc' AS timestamptz) AT TIME ZONE 'UTC' AS window_end
), excluded AS (
    SELECT unnest(string_to_array(NULLIF(:'exclude_user_ids', ''), ',')::bigint[]) AS user_id
),
-- BEGIN PORTABLE AGGREGATE CORE (fixture-tested without production access)
eligible_users AS (
    SELECT u.id, u.created_at
    FROM users u
    WHERE NOT EXISTS (SELECT 1 FROM excluded e WHERE e.user_id = u.id)
), completed AS (
    SELECT up.user_id, DATE(up.submitted_at) AS activity_date,
           LOWER(gp.skill) AS skill
    FROM user_practices up
    JOIN eligible_users u ON u.id = up.user_id
    JOIN generated_practices gp ON gp.id = up.practice_id
    CROSS JOIN params p
    WHERE up.submitted_at >= p.window_start AND up.submitted_at < p.window_end
), active_days AS (
    SELECT user_id, COUNT(DISTINCT activity_date) AS days
    FROM completed GROUP BY user_id
)
SELECT
    (SELECT window_start FROM params) AS window_start_utc_inclusive,
    (SELECT window_end FROM params) AS window_end_utc_exclusive,
    (SELECT COUNT(*) FROM eligible_users u CROSS JOIN params p
        WHERE u.created_at >= p.window_start AND u.created_at < p.window_end) AS signups,
    (SELECT COUNT(*) FROM active_days) AS active_learners_with_completion,
    (SELECT COUNT(*) FROM active_days WHERE days >= 2) AS returning_learners_two_utc_dates,
    (SELECT COUNT(*) FROM completed) AS completed_practices,
    (SELECT COUNT(*) FROM completed WHERE skill = 'writing') AS writing_completions,
    (SELECT COUNT(DISTINCT user_id) FROM completed WHERE skill = 'writing') AS writing_learners,
    (SELECT COUNT(*) FROM completed WHERE skill = 'speaking') AS speaking_completions,
    (SELECT COUNT(DISTINCT user_id) FROM completed WHERE skill = 'speaking') AS speaking_learners,
    (SELECT COUNT(*) FROM completed WHERE skill = 'reading') AS reading_completions,
    (SELECT COUNT(*) FROM completed WHERE skill = 'listening') AS listening_completions,
    (SELECT COUNT(*) FROM completed WHERE skill = 'grammar') AS grammar_completions,
    (SELECT COUNT(*) FROM generated_practices gp CROSS JOIN params p
        WHERE gp.generated_date >= p.window_start AND gp.generated_date < p.window_end) AS content_pool_rows_created_not_learner_activity;
ROLLBACK;
