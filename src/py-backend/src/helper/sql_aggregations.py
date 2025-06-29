from schemas import AggregationFeature

aggregation_sql_templates = [
    {
        "feature": AggregationFeature.context_switch,
        "sql_template": """
SELECT
  {time_grouping} AS {time_bucket},
  prev_activity AS "From",
  activity AS "To",
  COUNT(*) AS switch_count
FROM (
  SELECT
    tsStart,
    activity,
    LAG(activity) OVER (ORDER BY tsStart) AS prev_activity
  FROM window_activity
  WHERE {time_filter}
    AND {additional_conditions}
)
WHERE activity != prev_activity
GROUP BY time_bucket, prev_activity, activity
ORDER BY time_bucket ASC, switch_count DESC;
""".strip()
    },
    {
        "feature": AggregationFeature.total_focus_time,
        "sql_template": """
SELECT
  {time_grouping} AS {time_bucket},
  activity,
  processName,
  SUM(durationInSeconds) AS total_focus_time_in_s
FROM window_activity
WHERE
  {time_filter}
  AND {additional_conditions}
GROUP BY
  time_bucket,
  activity,
  processName,
  windowTitle
ORDER BY
  time_bucket ASC,
  total_focus_time_in_s DESC;
""".strip()
    },
    {
        "feature": AggregationFeature.input_activity_volume,
        "sql_template": """
SELECT
  {time_grouping} AS {time_bucket},
  SUM(keysTotal) AS total_keystrokes,
  SUM(clickTotal) AS total_clicks,
  ROUND(SUM(movedDistance), 2) AS total_mouse_movement,
  ROUND(SUM(scrollDelta), 2) AS total_scroll
FROM user_input
WHERE
  {time_filter}
  AND {additional_conditions}
GROUP BY
  time_bucket
ORDER BY
  time_bucket ASC;
""".strip()
    },
    {
        "feature": AggregationFeature.typing_streaks,
        "sql_template": """
SELECT
  {time_grouping} AS {time_bucket},
  COUNT(*) AS typing_streaks
FROM (
    SELECT 
      tsStart,
      LAG(tsEnd) OVER (ORDER BY tsStart) AS prev_end
    FROM user_input
    WHERE {time_filter}
      AND keysTotal > 0
      AND {additional_conditions}
)
WHERE strftime('%s', tsStart) - strftime('%s', prev_end) > 60
GROUP BY time_bucket
ORDER BY time_bucket ASC;
""".strip()
    },
    {
        "feature": AggregationFeature.typing_gaps,
        "sql_template": """
SELECT
  {time_grouping} AS {time_bucket},
  COUNT(*) AS typing_gaps
FROM (
    SELECT 
      tsStart,
      LAG(tsEnd) OVER (ORDER BY tsStart) AS prev_end
    FROM user_input
    WHERE {time_filter}
      AND keysTotal > 0
      AND {additional_conditions}
)
WHERE strftime('%s', tsStart) - strftime('%s', prev_end) >= 300
GROUP BY time_bucket
ORDER BY time_bucket ASC;
""".strip()
    },
    {
        "feature": AggregationFeature.user_input_by_app,
        "sql_template": """
SELECT
  {time_grouping} AS {time_bucket},
  w.activity,
  w.processName,
  SUM(u.keysTotal) AS total_keystrokes,
  SUM(u.clickTotal) AS total_clicks,
  ROUND(SUM(u.movedDistance), 2) AS total_mouse_movement,
  ROUND(SUM(u.scrollDelta), 2) AS total_scroll
FROM user_input u
JOIN window_activity w
  ON u.tsStart BETWEEN w.tsStart AND w.tsEnd
WHERE
  {time_filter}
  AND {additional_conditions}
GROUP BY
  time_bucket,
  w.activity,
  w.processName
ORDER BY
  time_bucket ASC,
  total_keystrokes DESC;

""".strip()
    },
    {
        "feature": AggregationFeature.activity_category_ratio,
        "sql_template": """
SELECT
  {time_grouping} AS {time_bucket},
  ROUND(
    SUM(CASE 
          WHEN activity IN ({category_list}) THEN durationInSeconds 
          ELSE 0 
        END) * 1.0 /
    SUM(durationInSeconds),
    2
  ) AS category_time_ratio
FROM window_activity
WHERE
  {time_filter}
  AND {additional_conditions}
GROUP BY
  time_bucket
ORDER BY
  time_bucket ASC;

""".strip()
    },
    {
        "feature": AggregationFeature.work_related_typing,
        "sql_template": """
SELECT
  {time_grouping} AS {time_bucket},
  ROUND(
    SUM(u.keysTotal) * 1.0 /
    SUM(w.durationInSeconds),
    2
  ) AS typing_productivity
FROM user_input u
JOIN window_activity w
  ON u.tsStart BETWEEN w.tsStart AND w.tsEnd
WHERE
  {time_filter}
  AND u.keysTotal > 0
  AND {additional_conditions}
GROUP BY
  time_bucket
ORDER BY
  time_bucket ASC;
""".strip()
    },
    {
        "feature": AggregationFeature.input_activity_by_productivity,
        "sql_template": """
SELECT
  {time_grouping} AS {time_bucket},
  s.response AS productivity_rating,
  {aggregation_fields}
FROM session s
JOIN user_input u
  ON u.tsStart BETWEEN s.tsStart AND s.tsEnd
WHERE
  {time_filter}
  AND {additional_conditions}
GROUP BY
  time_bucket,
  s.response
ORDER BY
  time_bucket ASC,
  s.response ASC;


""".strip()
    },
    {
        "feature": AggregationFeature.activity_time_by_productivity,
        "sql_template": """
SELECT
  {time_grouping} AS {time_bucket},
  s.response AS productivity_rating,
  {aggregation_fields}
FROM session s
JOIN window_activity w
  ON w.tsStart BETWEEN s.tsStart AND s.tsEnd
WHERE
  {time_filter}
  AND {additional_conditions}
GROUP BY
  time_bucket,
  s.response
ORDER BY
  time_bucket ASC,
  s.response ASC;
""".strip()
    },
    {
        "feature": AggregationFeature.session_activity_input_summary,
        "sql_template": """
WITH window_activity_agg AS (
  SELECT
    s.id AS session_id,
    {time_grouping} AS {time_bucket},
    {window_aggregations}
  FROM session s
  JOIN window_activity w
    ON w.tsStart BETWEEN s.tsStart AND s.tsEnd
  WHERE {time_filter}
    AND {additional_conditions}
  GROUP BY s.id, time_bucket
),
user_input_agg AS (
  SELECT
    s.id AS session_id,
    {time_grouping} AS {time_bucket},
    {user_aggregations}
  FROM session s
  JOIN user_input u
    ON u.tsStart BETWEEN s.tsStart AND s.tsEnd
  WHERE {time_filter}
    AND {additional_conditions}
  GROUP BY s.id, time_bucket
)
SELECT
  wa.time_bucket,
  s.response AS productivity_rating,
  {final_select_fields}
FROM window_activity_agg wa
LEFT JOIN user_input_agg ui
  ON wa.session_id = ui.session_id
  AND wa.time_bucket = ui.time_bucket
JOIN session s
  ON s.id = wa.session_id
ORDER BY
  wa.time_bucket ASC,
  s.response ASC;
""".strip()
    }
]


